// Import in denselben XCAF-Reader wie pythonocc; der Aufruf per CDLL haelt keine Python-Sperre.
#include <STEPCAFControl_Reader.hxx>
#include <TDocStd_Document.hxx>
#include <Message_ProgressIndicator.hxx>
#include <atomic>
#ifdef _WIN32
#define DG_EXPORT extern "C" __declspec(dllexport)
#else
#define DG_EXPORT extern "C" __attribute__((visibility("default")))
#endif

using Meldung = int (*)(int);

class Fortschritt final : public Message_ProgressIndicator {
public:
    explicit Fortschritt(Meldung melde) : melde_(melde) {}

private:
    void Show(const Message_ProgressScope&, bool) override {
        const int prozent = static_cast<int>(100 * GetPosition());
        if (prozent != zuletzt_) {
            zuletzt_ = prozent;
            if (!melde_(prozent)) abbruch_.store(true);
        }
    }
    bool UserBreak() override { return abbruch_.load(); }

    Meldung melde_;
    int zuletzt_ = -1;
    std::atomic<bool> abbruch_{false};
};

DG_EXPORT int dg_step_lesen(STEPCAFControl_Reader* reader, const char* pfad) noexcept {
    try {
        return reader->ReadFile(pfad) == IFSelect_RetDone;
    } catch (...) {
        return 0;
    }
}

DG_EXPORT int dg_step_uebertragen(STEPCAFControl_Reader* reader, const TDF_Label* label, Meldung melde) noexcept {
    try {
        const auto doc = TDocStd_Document::Get(*label);
        if (doc.IsNull()) return 0;
        occ::handle<Message_ProgressIndicator> stand;
        if (melde) stand = new Fortschritt(melde);
        return reader->Transfer(doc, Message_ProgressIndicator::Start(stand));
    } catch (...) {
        return 0;
    }
}
