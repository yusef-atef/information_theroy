import 'dart:math';
import 'dart:typed_data';
import 'mapping_engine.dart';
import 'reed_solomon.dart';

class RegistrationBundle {
  final List<int> codeword;
  final List<int> seed;
  
  RegistrationBundle({required this.codeword, required this.seed});
}

class CorrectionResult {
  final bool success;
  final String? correctedPassword;
  final int errorsCorrected;
  final int erasuresFilled;

  CorrectionResult({
    required this.success,
    this.correctedPassword,
    required this.errorsCorrected,
    required this.erasuresFilled,
  });
}

class EccAuth {
  /// Generate a secure 32-byte seed
  static List<int> _generateSeed() {
    final random = Random.secure();
    return List.generate(32, (_) => random.nextInt(256));
  }

  /// Encodes the master password for the first time
  static RegistrationBundle registerPassword(String password) {
    List<int> seed = _generateSeed();
    Map<int, int> mapping = MappingEngine.generateMapping(seed);
    
    var encodeResult = MappingEngine.encodePasswordWithErasures(password, mapping, '');
    List<int> messageSymbols = encodeResult['symbols'];

    int actualLen = min(password.length, MappingEngine.passwordBlockLen);
    int nParity = max(4, (actualLen ~/ 4) * 2);
    if (nParity % 2 != 0) nParity += 1;

    List<int> codeword = ReedSolomon.encode(messageSymbols, nParity);

    return RegistrationBundle(codeword: codeword, seed: seed);
  }

  /// Verifies and corrects an entered password based on stored parity and seed
  static CorrectionResult verifyAndCorrect(
    String inputPassword,
    List<int> storedCodeword,
    List<int> seed,
    [String erasureChar = '*']
  ) {
    Map<int, int> mapping = MappingEngine.generateMapping(seed);
    Map<int, int> inverseMapping = MappingEngine.generateInverseMapping(mapping);

    var encodeResult = MappingEngine.encodePasswordWithErasures(inputPassword, mapping, erasureChar);
    List<int> messageSymbols = encodeResult['symbols'];
    List<int> erasurePositions = encodeResult['erasurePositions'];

    // Graft parity symbols
    int nParity = storedCodeword.length - MappingEngine.passwordBlockLen;
    List<int> received = List.from(messageSymbols);
    received.addAll(storedCodeword.sublist(MappingEngine.passwordBlockLen));

    try {
      List<int> correctedMessage = ReedSolomon.decode(
        received, 
        nParity, 
        erasurePositions: erasurePositions
      );

      String correctedPassword = MappingEngine.decodeSymbols(correctedMessage, inverseMapping);
      
      // Append un-protected extra chars if any
      if (inputPassword.length > MappingEngine.passwordBlockLen) {
        correctedPassword += inputPassword.substring(MappingEngine.passwordBlockLen);
      }

      int errors = 0;
      for (int i = 0; i < messageSymbols.length; i++) {
        if (messageSymbols[i] != correctedMessage[i] && !erasurePositions.contains(i)) {
          errors++;
        }
      }

      return CorrectionResult(
        success: true,
        correctedPassword: correctedPassword,
        errorsCorrected: errors,
        erasuresFilled: erasurePositions.length,
      );
    } catch (e) {
      return CorrectionResult(
        success: false,
        errorsCorrected: 0,
        erasuresFilled: erasurePositions.length,
      );
    }
  }
}
