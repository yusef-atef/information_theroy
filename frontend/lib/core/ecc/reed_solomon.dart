import 'dart:math';
import 'gf256.dart';

class ReedSolomonError implements Exception {
  final String message;
  ReedSolomonError(this.message);
  @override
  String toString() => "ReedSolomonError: $message";
}

/// Reed-Solomon Encoder/Decoder over GF(256)
class ReedSolomon {
  // --- Little Endian Polynomial Helpers ---

  static List<int> _lePolyAdd(List<int> p, List<int> q) {
    int maxLen = max(p.length, q.length);
    List<int> res = List.filled(maxLen, 0);
    for (int i = 0; i < maxLen; i++) {
      int a = i < p.length ? p[i] : 0;
      int b = i < q.length ? q[i] : 0;
      res[i] = GF256.add(a, b);
    }
    return res;
  }

  static List<int> _lePolyMul(List<int> p, List<int> q) {
    if (p.isEmpty || q.isEmpty) return [];
    List<int> res = List.filled(p.length + q.length - 1, 0);
    for (int i = 0; i < p.length; i++) {
      if (p[i] == 0) continue;
      for (int j = 0; j < q.length; j++) {
        res[i + j] ^= GF256.mul(p[i], q[j]);
      }
    }
    return res;
  }

  static List<int> _lePolyScale(List<int> p, int s) {
    return p.map((pi) => GF256.mul(pi, s)).toList();
  }

  static int _lePolyEval(List<int> p, int x) {
    int res = 0;
    for (int i = p.length - 1; i >= 0; i--) {
      res = GF256.add(GF256.mul(res, x), p[i]);
    }
    return res;
  }

  // --- Encoder (Big Endian) ---

  /// Append nParity check symbols to the message
  static List<int> encode(List<int> message, int nParity) {
    GF256.init();
    List<int> gen = [1];
    for (int i = 0; i < nParity; i++) {
      gen = GF256.polyMul(gen, [1, GF256.pow(2, i)]);
    }

    List<int> padded = List.from(message)..addAll(List.filled(nParity, 0));
    List<List<int>> divResult = GF256.polyDiv(padded, gen);
    List<int> remainder = divResult[1];

    List<int> parity = List<int>.filled(nParity - remainder.length, 0, growable: true)..addAll(remainder);
    return List.from(message)..addAll(parity);
  }

  // --- Decoder ---

  /// Decode and correct received codeword
  static List<int> decode(List<int> codeword, int nParity, {List<int>? erasurePositions}) {
    GF256.init();
    erasurePositions ??= [];
    int n = codeword.length;

    // 1. Syndromes S_i = C(alpha^i)
    List<int> synd = [];
    for (int i = 0; i < nParity; i++) {
      synd.add(GF256.polyEval(codeword, GF256.pow(2, i)));
    }
    if (synd.every((s) => s == 0)) {
      return codeword.sublist(0, codeword.length - nParity);
    }

    // 2. Erasure locator Gamma(z)
    List<int> gamma = [1];
    for (int pos in erasurePositions) {
      int X = GF256.pow(2, n - 1 - pos);
      gamma = _lePolyMul(gamma, [1, X]);
    }

    // 3. Forney syndromes S'(z) = S(z) * Gamma(z)
    List<int> sPrime = _lePolyMul(synd, gamma);
    int nErasures = erasurePositions.length;
    
    // Bounds check to avoid sublist errors
    if (nErasures > nParity) {
      throw ReedSolomonError("Too many erasures");
    }
    
    List<int> errorSynd = sPrime.sublist(nErasures, sPrime.length > nParity ? nParity : sPrime.length);

    // 4. Berlekamp-Massey on error syndromes
    List<int> sigmaErr = [1];
    List<int> B = [1];
    int L = 0;
    int m = 1;
    int prevDiscrepancy = 1;

    for (int i = 0; i < errorSynd.length; i++) {
      int d = errorSynd[i];
      for (int j = 1; j <= L; j++) {
        if (j < sigmaErr.length) {
          d ^= GF256.mul(sigmaErr[j], errorSynd[i - j]);
        }
      }

      if (d == 0) {
        m += 1;
      } else if (2 * L <= i) {
        List<int> T = List.from(sigmaErr);
        int factor = GF256.div(d, prevDiscrepancy);
        List<int> zmB = List<int>.filled(m, 0, growable: true)..addAll(B);
        sigmaErr = _lePolyAdd(sigmaErr, _lePolyScale(zmB, factor));
        L = i + 1 - L;
        B = T;
        prevDiscrepancy = d;
        m = 1;
      } else {
        int factor = GF256.div(d, prevDiscrepancy);
        List<int> zmB = List<int>.filled(m, 0, growable: true)..addAll(B);
        sigmaErr = _lePolyAdd(sigmaErr, _lePolyScale(zmB, factor));
        m += 1;
      }
    }

    // 5. Full locator sigma(z) = sigma_err(z) * gamma(z)
    List<int> sigma = _lePolyMul(sigmaErr, gamma);

    // 6. Find all error/erasure positions via Chien search
    List<int> allErrorPos = [];
    for (int i = 0; i < n; i++) {
      int xInv = GF256.inv(GF256.pow(2, n - 1 - i));
      if (_lePolyEval(sigma, xInv) == 0) {
        allErrorPos.add(i);
      }
    }

    if (allErrorPos.length > nParity) {
      throw ReedSolomonError("Correction capacity exceeded");
    }

    // 7. Forney Algorithm for magnitudes
    List<int> omegaFull = _lePolyMul(synd, sigma);
    List<int> omega = omegaFull.length > nParity ? omegaFull.sublist(0, nParity) : omegaFull;

    List<int> sigmaPrime = List.filled(sigma.length - 1, 0);
    for (int i = 1; i < sigma.length; i++) {
      if (i % 2 == 1) {
        sigmaPrime[i - 1] = sigma[i];
      }
    }

    List<int> newCw = List.from(codeword);
    for (int i in allErrorPos) {
      int X = GF256.pow(2, n - 1 - i);
      int xInv = GF256.inv(X);
      int num = _lePolyEval(omega, xInv);
      int den = _lePolyEval(sigmaPrime, xInv);
      if (den == 0) continue;

      int mag = GF256.mul(X, GF256.div(num, den));
      newCw[i] ^= mag;
    }

    // Final verification
    for (int j = 0; j < nParity; j++) {
      if (GF256.polyEval(newCw, GF256.pow(2, j)) != 0) {
        throw ReedSolomonError("Reed-Solomon correction failed");
      }
    }

    return newCw.sublist(0, newCw.length - nParity);
  }
}
