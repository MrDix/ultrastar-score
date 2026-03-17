/**
 * ptAKF pitch detection algorithm header.
 *
 * Based on Vocaluxe's ptAKF implementation (GPL v3).
 * Original: https://github.com/Vocaluxe/Vocaluxe
 */

#ifndef ULTRASTAR_SCORE_PTAKF_H
#define ULTRASTAR_SCORE_PTAKF_H

#include <vector>

namespace ultrastar_score {

struct PitchResult {
    int tone;           // Halftone index (0=C2, 12=C3, ..., 56=G#6), -1 if unvoiced
    double frequency;   // Detected frequency in Hz, 0 if unvoiced
    double confidence;  // 0.0 to 1.0
};

class PtAKF {
public:
    /**
     * @param sample_rate Audio sample rate (typically 44100)
     */
    explicit PtAKF(int sample_rate = 44100);

    /**
     * Detect pitch in a single window of samples.
     *
     * @param samples Audio samples (mono, normalized to [-1, 1])
     * @param num_samples Number of samples (must be >= 2048)
     * @param volume_threshold Minimum volume to attempt detection (0.0-1.0)
     * @return PitchResult with detected tone, frequency, and confidence
     */
    PitchResult detect(const double* samples, int num_samples,
                       double volume_threshold = 0.01) const;

    /**
     * Detect pitch across multiple frames with hop size and median smoothing.
     *
     * @param samples Full audio buffer (mono, normalized to [-1, 1])
     * @param num_samples Total number of samples
     * @param hop_size Hop size in samples (default 1024)
     * @param volume_threshold Minimum volume to attempt detection
     * @return Vector of PitchResult, one per frame
     */
    std::vector<PitchResult> detect_multi(
        const double* samples, int num_samples,
        int hop_size = 1024,
        double volume_threshold = 0.01
    ) const;

    static constexpr int window_size() { return 2048; }
    static constexpr double base_freq() { return 65.4064; }
    static constexpr int max_halftone() { return 56; }

private:
    int sample_rate_;
    std::vector<double> hamming_;
    std::vector<double> samples_per_period_;
    std::vector<double> samples_per_period_lo_;
    std::vector<double> samples_per_period_hi_;
};

}  // namespace ultrastar_score

#endif  // ULTRASTAR_SCORE_PTAKF_H
