import 'dart:math';
import 'dart:convert';
import 'package:crypto/crypto.dart';

class MappingEngine {
  static const int passwordBlockLen = 64;
  
  // Extended printable characters (32 to 255), excluding '*' (42)
  static final List<int> _printable = List.generate(224, (i) => i + 32).where((c) => c != 42).toList();

  /// Simple deterministic PRNG to ensure cross-platform identical shuffling
  static int _xorshift32(int state) {
    state ^= (state << 13) & 0xFFFFFFFF;
    state ^= (state >> 17);
    state ^= (state << 5) & 0xFFFFFFFF;
    return state;
  }

  /// Generate a unique mapping table from a seed
  static Map<int, int> generateMapping(List<int> seed) {
    final digest = sha256.convert(seed).bytes;
    // Extract a 32-bit integer from the first 4 bytes of the hash
    int rngState = (digest[0] << 24) | (digest[1] << 16) | (digest[2] << 8) | digest[3];
    if (rngState == 0) rngState = 1;

    List<int> gfSymbols = List.generate(255, (i) => i + 1); // 1 to 255

    // Fisher-Yates shuffle
    for (int i = gfSymbols.length - 1; i > 0; i--) {
      rngState = _xorshift32(rngState);
      int j = rngState.abs() % (i + 1);
      int temp = gfSymbols[i];
      gfSymbols[i] = gfSymbols[j];
      gfSymbols[j] = temp;
    }

    Map<int, int> mapping = {};
    for (int i = 0; i < _printable.length; i++) {
      mapping[_printable[i]] = gfSymbols[i];
    }
    return mapping;
  }

  static Map<int, int> generateInverseMapping(Map<int, int> mapping) {
    Map<int, int> inverse = {};
    mapping.forEach((key, value) {
      inverse[value] = key;
    });
    return inverse;
  }

  static Map<String, dynamic> encodePasswordWithErasures(String password, Map<int, int> mapping, [String erasureChar = '*']) {
    String pw = password.length > passwordBlockLen ? password.substring(0, passwordBlockLen) : password;
    int padChar = ' '.codeUnitAt(0);
    int padSymbol = mapping[padChar] ?? 1;

    List<int> symbols = [];
    List<int> erasurePositions = [];

    for (int i = 0; i < pw.length; i++) {
      String ch = pw[i];
      if (ch == erasureChar) {
        erasurePositions.add(i);
        symbols.add(0); // 0 denotes erasure
      } else {
        int code = ch.codeUnitAt(0);
        symbols.add(mapping[code] ?? padSymbol);
      }
    }

    // Pad
    while (symbols.length < passwordBlockLen) {
      symbols.add(padSymbol);
    }

    return {
      'symbols': symbols,
      'erasurePositions': erasurePositions,
    };
  }

  static String decodeSymbols(List<int> symbols, Map<int, int> inverseMapping) {
    StringBuffer sb = StringBuffer();
    for (int sym in symbols) {
      int code = inverseMapping[sym] ?? ' '.codeUnitAt(0);
      sb.writeCharCode(code);
    }
    return sb.toString().trimRight(); // Remove padding
  }
}
