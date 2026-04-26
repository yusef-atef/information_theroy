import 'dart:typed_data';

/// Galois Field Arithmetic over GF(256)
/// 
/// Implements GF(2^8) using primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 (0x11D).
/// Uses precomputed log and antilog tables for O(1) multiply/divide.
class GF256 {
  static const int _primPoly = 0x11D;
  static const int _fieldSize = 256;

  static final Int32List _log = Int32List(_fieldSize);
  static final Int32List _exp = Int32List(_fieldSize * 2);

  static bool _initialized = false;

  /// Initializes the precomputed log and antilog tables.
  /// Must be called once before using multiplication/division.
  static void init() {
    if (_initialized) return;

    int x = 1;
    for (int i = 0; i < _fieldSize - 1; i++) {
      _exp[i] = x;
      _log[x] = i;
      x <<= 1;
      if (x >= _fieldSize) {
        x ^= _primPoly;
        x &= 0xFF;
      }
    }

    // Mirror the first 255 entries into positions [255..509]
    for (int i = _fieldSize - 1; i < _fieldSize * 2; i++) {
      _exp[i] = _exp[i - (_fieldSize - 1)];
    }

    _initialized = true;
  }

  /// Addition in GF(256) - XOR
  static int add(int a, int b) => a ^ b;

  /// Subtraction in GF(256) - XOR (same as addition)
  static int sub(int a, int b) => a ^ b;

  /// Multiplication in GF(256)
  static int mul(int a, int b) {
    if (a == 0 || b == 0) return 0;
    return _exp[_log[a] + _log[b]];
  }

  /// Division in GF(256)
  static int div(int a, int b) {
    if (b == 0) throw Exception("Division by zero in GF(256)");
    if (a == 0) return 0;
    return _exp[(_log[a] - _log[b]) % (_fieldSize - 1)];
  }

  /// Power in GF(256)
  static int pow(int a, int power) {
    if (power == 0) return 1;
    if (a == 0) return 0;
    return _exp[(_log[a] * power) % (_fieldSize - 1)];
  }

  /// Multiplicative inverse
  static int inv(int a) {
    if (a == 0) throw Exception("No inverse of 0 in GF(256)");
    return _exp[(_fieldSize - 1) - _log[a]];
  }

  // --- Polynomial Operations ---

  /// Multiply a polynomial by a scalar
  static List<int> polyScale(List<int> poly, int scalar) {
    return poly.map((c) => mul(c, scalar)).toList();
  }

  /// Add two polynomials
  static List<int> polyAdd(List<int> p, List<int> q) {
    List<int> pAligned = List.from(p);
    List<int> qAligned = List.from(q);

    if (pAligned.length < qAligned.length) {
      pAligned.insertAll(0, List.filled(qAligned.length - pAligned.length, 0));
    } else if (qAligned.length < pAligned.length) {
      qAligned.insertAll(0, List.filled(pAligned.length - qAligned.length, 0));
    }

    List<int> result = [];
    for (int i = 0; i < pAligned.length; i++) {
      result.add(add(pAligned[i], qAligned[i]));
    }
    return result;
  }

  /// Multiply two polynomials
  static List<int> polyMul(List<int> p, List<int> q) {
    List<int> result = List.filled(p.length + q.length - 1, 0);
    for (int i = 0; i < p.length; i++) {
      for (int j = 0; j < q.length; j++) {
        result[i + j] ^= mul(p[i], q[j]);
      }
    }
    return result;
  }

  /// Evaluate polynomial at x using Horner's method
  static int polyEval(List<int> poly, int x) {
    int result = 0;
    for (int coeff in poly) {
      result = add(mul(result, x), coeff);
    }
    return result;
  }

  /// Polynomial division
  /// Returns [quotient, remainder]
  static List<List<int>> polyDiv(List<int> dividend, List<int> divisor) {
    List<int> msgOut = List.from(dividend);
    for (int i = 0; i < dividend.length - (divisor.length - 1); i++) {
      int coef = msgOut[i];
      if (coef != 0) {
        for (int j = 1; j < divisor.length; j++) {
          if (divisor[j] != 0) {
            msgOut[i + j] ^= mul(divisor[j], coef);
          }
        }
      }
    }
    int separator = dividend.length - (divisor.length - 1);
    return [
      msgOut.sublist(0, separator),
      msgOut.sublist(separator)
    ];
  }
}
