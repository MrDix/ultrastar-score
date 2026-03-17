/**
 * pybind11 bindings for ptAKF pitch detection.
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "ptakf.h"

namespace py = pybind11;

PYBIND11_MODULE(_ptakf, m) {
    m.doc() = "Vocaluxe ptAKF pitch detection (AKF/AMDF hybrid)";

    using namespace ultrastar_score;

    py::class_<PitchResult>(m, "PitchResult")
        .def(py::init<>())
        .def_readwrite("tone", &PitchResult::tone,
            "Halftone index (0=C2, 12=C3, ..., 56=G#6), -1 if unvoiced")
        .def_readwrite("frequency", &PitchResult::frequency,
            "Detected frequency in Hz, 0 if unvoiced")
        .def_readwrite("confidence", &PitchResult::confidence,
            "Detection confidence 0.0 to 1.0")
        .def("__repr__", [](const PitchResult& r) {
            if (r.tone < 0)
                return std::string("PitchResult(unvoiced)");
            const char* names[] = {"C", "C#", "D", "D#", "E", "F",
                                   "F#", "G", "G#", "A", "A#", "B"};
            int note = r.tone % 12;
            int octave = r.tone / 12 + 2;
            return std::string("PitchResult(") + names[note] +
                   std::to_string(octave) + ", " +
                   std::to_string(r.frequency).substr(0, 6) + " Hz, " +
                   "conf=" + std::to_string(r.confidence).substr(0, 4) + ")";
        });

    py::class_<PtAKF>(m, "PtAKF")
        .def(py::init<int>(), py::arg("sample_rate") = 44100,
            "Create pitch detector with given sample rate")
        .def("detect",
            [](const PtAKF& self, py::array_t<double> samples, double volume_threshold) {
                auto buf = samples.request();
                if (buf.ndim != 1)
                    throw std::runtime_error("Expected 1-D array");
                return self.detect(
                    static_cast<const double*>(buf.ptr),
                    static_cast<int>(buf.shape[0]),
                    volume_threshold
                );
            },
            py::arg("samples"), py::arg("volume_threshold") = 0.01,
            "Detect pitch in a single window (>= 2048 samples)")
        .def("detect_multi",
            [](const PtAKF& self, py::array_t<double> samples,
               int hop_size, double volume_threshold) {
                auto buf = samples.request();
                if (buf.ndim != 1)
                    throw std::runtime_error("Expected 1-D array");
                return self.detect_multi(
                    static_cast<const double*>(buf.ptr),
                    static_cast<int>(buf.shape[0]),
                    hop_size,
                    volume_threshold
                );
            },
            py::arg("samples"), py::arg("hop_size") = 1024,
            py::arg("volume_threshold") = 0.01,
            "Detect pitch across frames with median smoothing")
        .def_property_readonly_static("WINDOW_SIZE",
            [](py::object) { return PtAKF::window_size(); })
        .def_property_readonly_static("BASE_FREQ",
            [](py::object) { return PtAKF::base_freq(); })
        .def_property_readonly_static("MAX_HALFTONE",
            [](py::object) { return PtAKF::max_halftone(); });
}
