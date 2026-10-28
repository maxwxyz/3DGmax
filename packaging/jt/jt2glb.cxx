// jt2glb – JT-Datei mit TKJT lesen und als glTF-Binaerdatei (GLB) schreiben (Teil von 3DGmax, GPL-3.0-or-later).
//
// Aufruf: jt2glb eingabe.jt ausgabe.glb
// Struktur (Partition, Gruppe, Teil, Instanz) wird zur XCAF-Baugruppe mit Namen und Lagen, die Dreiecke der
// hoechsten Detailstufe zu Flaechen mit Triangulation, die Diffusfarbe des Materials zur Flaechenfarbe. Externe
// Partitionen (Monolith-Dateien mit Verweisen) laedt TKJT selbst. Kein B-Rep, keine PMI (Stufe 1).
// TKJT (Open Cascade, GPL v2+), Fork mit JT 10: https://github.com/wwmayer/TKJT – nur in der Build-Variante mit JT.

#include <JtAttribute_GeometricTransform.hxx>
#include <JtAttribute_Material.hxx>
#include <JtData_Model.hxx>
#include <JtElement_ShapeLOD_Vertex.hxx>
#include <JtNode_Group.hxx>
#include <JtNode_Instance.hxx>
#include <JtNode_Partition.hxx>
#include <JtNode_RangeLOD.hxx>
#include <JtNode_Shape_Base.hxx>
#include <JtProperty_LateLoaded.hxx>

#include <BRep_Builder.hxx>
#include <Message_ProgressRange.hxx>
#include <Poly_Triangulation.hxx>
#include <Quantity_Color.hxx>
#include <RWGltf_CafWriter.hxx>
#include <TColStd_IndexedDataMapOfStringString.hxx>
#include <TCollection_AsciiString.hxx>
#include <TCollection_ExtendedString.hxx>
#include <TDataStd_Name.hxx>
#include <TDocStd_Document.hxx>
#include <TopLoc_Location.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Face.hxx>
#include <XCAFDoc_ColorTool.hxx>
#include <XCAFDoc_DocumentTool.hxx>
#include <XCAFDoc_ShapeTool.hxx>
#include <gp_Trsf.hxx>

#include <iostream>
#include <map>

namespace
{
struct Wandler
{
  Handle(TDocStd_Document) Doc;
  Handle(XCAFDoc_ShapeTool) Formen;
  Handle(XCAFDoc_ColorTool) Farben;
  int Dreiecke = 0;

  // Lage und Farbe aus den Attributen eines Knotens
  static void Attribute (const Handle(JtNode_Base)& theKnoten, gp_Trsf& theLage, bool& theHatFarbe,
                         Quantity_Color& theFarbe)
  {
    const JtData_Object::VectorOfObjects& anAttr = theKnoten->Attributes();
    for (Standard_Size i = 0; i < anAttr.Count(); ++i)
    {
      if (Handle(JtAttribute_GeometricTransform) aT = Handle(JtAttribute_GeometricTransform)::DownCast (anAttr[i]))
        aT->GetTrsf (theLage);
      else if (Handle(JtAttribute_Material) aM = Handle(JtAttribute_Material)::DownCast (anAttr[i]))
      {
        const Jt_F32* c = aM->DiffuseColor();
        theFarbe = Quantity_Color (c[0], c[1], c[2], Quantity_TOC_sRGB);
        theHatFarbe = true;
      }
    }
  }

  static void Benenne (const TDF_Label& theLabel, const TCollection_ExtendedString& theName)
  {
    if (theName.Length() > 0)
      TDataStd_Name::Set (theLabel, theName);
  }

  // Dreiecke der ersten (feinsten) Detailstufe einer Form als Flaeche mit Triangulation
  bool Form (const Handle(JtNode_Shape_Base)& theForm, TopoDS_Face& theFlaeche)
  {
    const JtData_Object::VectorOfLateLoads& aLaden = theForm->LateLoads();
    for (Standard_Size i = 0; i < aLaden.Count(); ++i)
    {
      aLaden[i]->Load();
      Handle(JtElement_ShapeLOD_Vertex) aLOD = Handle(JtElement_ShapeLOD_Vertex)::DownCast (aLaden[i]->DefferedObject());
      if (aLOD.IsNull())
        continue;
      const JtElement_ShapeLOD_Vertex::VertexData& aPunkte = aLOD->Vertices();
      const JtElement_ShapeLOD_Vertex::IndicesVec& aIdx = aLOD->Indices();
      const int aNbTri = (int) aIdx.Count() / 3;
      if (aPunkte.Count() == 0 || aNbTri == 0)
        continue;
      Handle(Poly_Triangulation) aTri = new Poly_Triangulation ((int) aPunkte.Count(), aNbTri, false);
      for (int p = 0; p < (int) aPunkte.Count(); ++p)
        aTri->SetNode (p + 1, gp_Pnt (aPunkte[p][0], aPunkte[p][1], aPunkte[p][2]));
      for (int t = 0; t < aNbTri; ++t)
        aTri->SetTriangle (t + 1, Poly_Triangle (aIdx[3 * t] + 1, aIdx[3 * t + 1] + 1, aIdx[3 * t + 2] + 1));
      aTri->ComputeNormals();
      BRep_Builder aB;
      aB.MakeFace (theFlaeche, aTri);
      Dreiecke += aNbTri;
      aLaden[i]->Unload();
      return true;
    }
    return false;
  }

  // Ergebnis eines Knotens: Label (Teil oder Baugruppe), Lage im Elternknoten, Name
  struct Eintrag
  {
    TDF_Label Label;
    TopLoc_Location Lage;
    TCollection_ExtendedString Name;
  };

  // Knoten als XCAF-Eintrag; leeres Label, wenn nichts Sichtbares darunter liegt
  Eintrag Knoten (const Handle(JtData_Object)& theObjekt, const Quantity_Color* theFarbe)
  {
    Handle(JtNode_Base) aKnoten = Handle(JtNode_Base)::DownCast (theObjekt);
    if (aKnoten.IsNull())
      return Eintrag();
    gp_Trsf aLage;
    bool aHatFarbe = false;
    Quantity_Color aFarbe;
    Attribute (aKnoten, aLage, aHatFarbe, aFarbe);
    const Quantity_Color* aGilt = aHatFarbe ? &aFarbe : theFarbe;

    if (Handle(JtNode_Instance) aInst = Handle(JtNode_Instance)::DownCast (aKnoten))
    {
      const Standard_Transient* aSchluessel = aInst->Object().get();
      auto aGefunden = Vorlagen.find (aSchluessel);
      if (aGefunden == Vorlagen.end())
        aGefunden = Vorlagen.emplace (aSchluessel, Knoten (aInst->Object(), aGilt)).first;
      const Eintrag& aVorlage = aGefunden->second;
      return Eintrag {aVorlage.Label, TopLoc_Location (aLage) * aVorlage.Lage,
                      aInst->Name().Length() > 0 ? aInst->Name() : aVorlage.Name};
    }
    if (Handle(JtNode_Shape_Base) aForm = Handle(JtNode_Shape_Base)::DownCast (aKnoten))
    {
      TopoDS_Face aFlaeche;
      if (!Form (aForm, aFlaeche))
        return Eintrag();
      TDF_Label aTeil = Formen->AddShape (aFlaeche, false);
      Benenne (aTeil, aForm->Name());
      if (aGilt != nullptr)
        Farben->SetColor (aTeil, *aGilt, XCAFDoc_ColorSurf);
      return Eintrag {aTeil, TopLoc_Location (aLage), aForm->Name()};
    }
    if (Handle(JtNode_Group) aGruppe = Handle(JtNode_Group)::DownCast (aKnoten))
    {
      if (Handle(JtNode_Partition) aPart = Handle(JtNode_Partition)::DownCast (aGruppe))
        if (aPart->Children().Count() == 0 && aPart->FileName().Length() > 0)
          aPart->Load();  // externe Partition (eigene Datei)
      const JtData_Object::VectorOfObjects& aKinder = aGruppe->Children();
      // Detailstufen: nur die feinste lesbare Stufe (ist sie nicht dekodierbar, die naechstgroebere)
      const bool aStufen = !Handle(JtNode_RangeLOD)::DownCast (aGruppe).IsNull();
      TDF_Label aBaugruppe;
      for (Standard_Size i = 0; i < aKinder.Count(); ++i)
      {
        Eintrag aKind = Knoten (aKinder[i], aGilt);
        if (aKind.Label.IsNull())
          continue;
        if (aBaugruppe.IsNull())
        {
          aBaugruppe = Formen->NewShape();
          Benenne (aBaugruppe, aGruppe->Name());
        }
        TDF_Label aKomp = Formen->AddComponent (aBaugruppe, aKind.Label, aKind.Lage);
        Benenne (aKomp, aKind.Name);
        if (aStufen)
          break;
      }
      if (aBaugruppe.IsNull())
        return Eintrag();
      return Eintrag {aBaugruppe, TopLoc_Location (aLage), aGruppe->Name()};
    }
    return Eintrag();
  }

  std::map<const Standard_Transient*, Eintrag> Vorlagen;  // geteilte Knoten (Instanzen) nur einmal
};
}

int main (int argc, char** argv)
{
  if (argc != 3)
  {
    std::cerr << "Aufruf: jt2glb eingabe.jt ausgabe.glb\n";
    return 2;
  }
  Wandler w;
  w.Doc = new TDocStd_Document ("BinXCAF");
  w.Formen = XCAFDoc_DocumentTool::ShapeTool (w.Doc->Main());
  w.Farben = XCAFDoc_DocumentTool::ColorTool (w.Doc->Main());
  XCAFDoc_DocumentTool::SetLengthUnit (w.Doc, 0.001);  // JT-Koordinaten werden als Millimeter weitergegeben

  Handle(JtData_Model) aModell = new JtData_Model (TCollection_ExtendedString (argv[1], true));
  Handle(JtNode_Partition) aWurzel = aModell->Init();
  if (aWurzel.IsNull())
  {
    std::cerr << "JT-Datei nicht lesbar: " << argv[1] << "\n";
    return 1;
  }
  if (w.Knoten (aWurzel, nullptr).Label.IsNull() || w.Dreiecke == 0)
  {
    std::cerr << "Keine Dreiecksdaten in der JT-Datei (nur B-Rep/XT oder leer)\n";
    return 1;
  }
  w.Formen->UpdateAssemblies();
  RWGltf_CafWriter aSchreiber (TCollection_AsciiString (argv[2]), true);
  TColStd_IndexedDataMapOfStringString aInfo;
  aInfo.Add ("generator", "3DGmax jt2glb (TKJT)");
  if (!aSchreiber.Perform (w.Doc, aInfo, Message_ProgressRange()))
  {
    std::cerr << "GLB nicht geschrieben: " << argv[2] << "\n";
    return 1;
  }
  std::cout << "JT2GLB OK: " << w.Dreiecke << " Dreiecke, Version " << aModell->MajorVersion() << "."
            << aModell->MinorVersion() << "\n";
  return 0;
}
