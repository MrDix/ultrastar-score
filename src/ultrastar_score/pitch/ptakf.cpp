/**
 * ptAKF pitch detection algorithm.
 *
 * Based on Vocaluxe's ptAKF implementation (GPL v3), which uses the combined
 * AKF/AMDF method from Kobayashi & Shimamura (2001):
 *
 *   f(tau) = AKF(tau) / (AMDF(tau) + 1)
 *
 * where AKF = autocorrelation, AMDF = average magnitude difference function.
 * Dividing AKF by (AMDF+1) sharpens pitch peaks significantly.
 *
 * Original: https://github.com/Vocaluxe/Vocaluxe (PitchTracker/ptAKF.cpp)
 * License: GPL v3
 */

#include "ptakf.h"
#include <cmath>
#include <algorithm>
#include <numeric>
#include <cstring>

namespace ultrastar_score {

static constexpr double BASE_FREQ = 65.4064;  // C2
static constexpr int MAX_HALFTONE = 56;        // C2 to G#6 (57 tones)
static constexpr int WINDOW_SIZE = 2048;
static constexpr double PI = 3.14159265358979323846;
static constexpr double AKF_VALIDATION_THRESHOLD = 0.33;

PtAKF::PtAKF(int sample_rate)
    : sample_rate_(sample_rate)
    , hamming_(WINDOW_SIZE)
    , samples_per_period_(MAX_HALFTONE + 1)
    , samples_per_period_lo_(MAX_HALFTONE + 1)
    , samples_per_period_hi_(MAX_HALFTONE + 1)
{
    // Pre-compute Hamming window
    for (int i = 0; i < WINDOW_SIZE; ++i) {
        hamming_[i] = 0.54 - 0.46 * std::cos(2.0 * PI * i / (WINDOW_SIZE - 1));
    }

    // Pre-compute samples per period for each halftone
    for (int tone = 0; tone <= MAX_HALFTONE; ++tone) {
        double freq = BASE_FREQ * std::pow(2.0, tone / 12.0);
        samples_per_period_[tone] = static_cast<double>(sample_rate_) / freq;

        // Fine-tuning: +/- 1/3 semitone
        double freq_lo = BASE_FREQ * std::pow(2.0, (tone - 1.0 / 3.0) / 12.0);
        double freq_hi = BASE_FREQ * std::pow(2.0, (tone + 1.0 / 3.0) / 12.0);
        samples_per_period_lo_[tone] = static_cast<double>(sample_rate_) / freq_lo;
        samples_per_period_hi_[tone] = static_cast<double>(sample_rate_) / freq_hi;
    }
}

/**
 * Compute AKF (autocorrelation) at a fractional lag using linear interpolation.
 */
static double akf_at_lag(const double* windowed, int n, double lag) {
    int lag_int = static_cast<int>(lag);
    double frac = lag - lag_int;

    if (lag_int + 1 >= n) return 0.0;

    double sum0 = 0.0, sum1 = 0.0;
    int count = n - lag_int - 1;

    for (int i = 0; i < count; ++i) {
        sum0 += windowed[i] * windowed[i + lag_int];
        sum1 += windowed[i] * windowed[i + lag_int + 1];
    }

    return (sum0 * (1.0 - frac) + sum1 * frac) / count;
}

/**
 * Compute AMDF at a fractional lag using linear interpolation.
 */
static double amdf_at_lag(const double* windowed, int n, double lag) {
    int lag_int = static_cast<int>(lag);
    double frac = lag - lag_int;

    if (lag_int + 1 >= n) return 1e9;

    double sum0 = 0.0, sum1 = 0.0;
    int count = n - lag_int - 1;

    for (int i = 0; i < count; ++i) {
        sum0 += std::abs(windowed[i] - windowed[i + lag_int]);
        sum1 += std::abs(windowed[i] - windowed[i + lag_int + 1]);
    }

    return (sum0 * (1.0 - frac) + sum1 * frac) / count;
}

PitchResult PtAKF::detect(const double* samples, int num_samples, double volume_threshold) const {
    PitchResult result;
    result.tone = -1;
    result.frequency = 0.0;
    result.confidence = 0.0;

    if (num_samples < WINDOW_SIZE) return result;

    // Volume check: max absolute value in second half
    double max_vol = 0.0;
    for (int i = WINDOW_SIZE / 2; i < WINDOW_SIZE; ++i) {
        double v = std::abs(samples[i]);
        if (v > max_vol) max_vol = v;
    }
    if (max_vol < volume_threshold) return result;

    // Apply Hamming window
    std::vector<double> windowed(WINDOW_SIZE);
    for (int i = 0; i < WINDOW_SIZE; ++i) {
        windowed[i] = samples[i] * hamming_[i];
    }

    // Compute AKF at lag 0 (signal energy) for validation
    double energy = 0.0;
    for (int i = 0; i < WINDOW_SIZE; ++i) {
        energy += windowed[i] * windowed[i];
    }
    energy /= WINDOW_SIZE;

    if (energy < 1e-10) return result;

    // Find the zero-crossing boundary of the lag-0 peak
    // (to avoid detecting the lag-0 autocorrelation peak itself)
    int zero_cross = 1;
    for (int i = 1; i < WINDOW_SIZE / 2; ++i) {
        double akf_val = akf_at_lag(windowed.data(), WINDOW_SIZE, i);
        if (akf_val <= 0) {
            zero_cross = i;
            break;
        }
    }

    // Compute combined AKF/AMDF weight for each halftone
    std::vector<double> weights(MAX_HALFTONE + 1, 0.0);
    std::vector<double> akf_values(MAX_HALFTONE + 1, 0.0);

    for (int tone = 0; tone <= MAX_HALFTONE; ++tone) {
        double lag = samples_per_period_[tone];

        // Skip if this tone's period is within the lag-0 peak
        if (lag < zero_cross) continue;
        if (lag >= WINDOW_SIZE / 2) continue;

        double akf = akf_at_lag(windowed.data(), WINDOW_SIZE, lag);
        double amdf = amdf_at_lag(windowed.data(), WINDOW_SIZE, lag);

        akf_values[tone] = akf;
        weights[tone] = akf / (amdf + 1.0);
    }

    // Find the best tone (peak in weights)
    int best_tone = -1;
    double best_weight = 0.0;

    for (int tone = 0; tone <= MAX_HALFTONE; ++tone) {
        if (weights[tone] > best_weight) {
            best_weight = weights[tone];
            best_tone = tone;
        }
    }

    if (best_tone < 0) return result;

    // Fine-tuning: check +/- 1/3 semitone offsets
    double fine_weight = best_weight;
    double fine_lag = samples_per_period_[best_tone];

    double lag_lo = samples_per_period_lo_[best_tone];
    double lag_hi = samples_per_period_hi_[best_tone];

    if (lag_lo >= zero_cross && lag_lo < WINDOW_SIZE / 2) {
        double akf_lo = akf_at_lag(windowed.data(), WINDOW_SIZE, lag_lo);
        double amdf_lo = amdf_at_lag(windowed.data(), WINDOW_SIZE, lag_lo);
        double w_lo = akf_lo / (amdf_lo + 1.0);
        if (w_lo > fine_weight) {
            fine_weight = w_lo;
            fine_lag = lag_lo;
        }
    }

    if (lag_hi >= zero_cross && lag_hi < WINDOW_SIZE / 2) {
        double akf_hi = akf_at_lag(windowed.data(), WINDOW_SIZE, lag_hi);
        double amdf_hi = amdf_at_lag(windowed.data(), WINDOW_SIZE, lag_hi);
        double w_hi = akf_hi / (amdf_hi + 1.0);
        if (w_hi > fine_weight) {
            fine_weight = w_hi;
            fine_lag = lag_hi;
        }
    }

    // Validation: AKF at detected lag must be >= 33% of signal energy
    double akf_final = akf_at_lag(windowed.data(), WINDOW_SIZE, fine_lag);
    if (akf_final < AKF_VALIDATION_THRESHOLD * energy) {
        return result;
    }

    result.tone = best_tone;
    result.frequency = static_cast<double>(sample_rate_) / fine_lag;
    result.confidence = std::min(1.0, akf_final / energy);

    return result;
}

std::vector<PitchResult> PtAKF::detect_multi(
    const double* samples,
    int num_samples,
    int hop_size,
    double volume_threshold
) const {
    std::vector<PitchResult> results;

    if (num_samples < WINDOW_SIZE) return results;

    int num_frames = (num_samples - WINDOW_SIZE) / hop_size + 1;
    results.reserve(num_frames);

    for (int i = 0; i < num_frames; ++i) {
        results.push_back(detect(samples + i * hop_size, WINDOW_SIZE, volume_threshold));
    }

    // Median smoothing over 3 consecutive frames
    if (results.size() >= 3) {
        std::vector<PitchResult> smoothed = results;
        for (size_t i = 1; i + 1 < results.size(); ++i) {
            int tones[3] = { results[i - 1].tone, results[i].tone, results[i + 1].tone };
            std::sort(tones, tones + 3);
            smoothed[i].tone = tones[1];  // median
            if (smoothed[i].tone >= 0) {
                smoothed[i].frequency = BASE_FREQ * std::pow(2.0, smoothed[i].tone / 12.0);
            }
        }
        return smoothed;
    }

    return results;
}

}  // namespace ultrastar_score
