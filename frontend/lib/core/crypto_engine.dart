import 'dart:convert';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'package:encrypt/encrypt.dart' as enc;
import 'package:pointycastle/asymmetric/api.dart' as pc;

class CryptoEngine {
  static final _cipher = AesGcm.with256bits();

  /// Derives a 32-byte key from a password and salt using PBKDF2.
  static Future<SecretKey> deriveKey(String password, String salt) async {
    final pbkdf2 = Pbkdf2(
      macAlgorithm: Hmac.sha256(),
      iterations: 10000,
      bits: 256,
    );
    final secretKey = await pbkdf2.deriveKeyFromPassword(
      password: password,
      nonce: utf8.encode(salt),
    );
    return secretKey;
  }

  /// Encrypts data using AES-256-GCM.
  /// Returns a concatenation of IV + Tag + Ciphertext.
  static Future<Uint8List> encryptData(Uint8List data, SecretKey key) async {
    final secretBox = await _cipher.encrypt(
      data,
      secretKey: key,
    );
    // Concatenate nonce (12 bytes) + tag (16 bytes) + ciphertext
    final result = BytesBuilder();
    result.add(secretBox.nonce);
    result.add(secretBox.mac.bytes);
    result.add(secretBox.cipherText);
    return result.toBytes();
  }

  /// Decrypts data using AES-256-GCM.
  static Future<Uint8List> decryptData(Uint8List encryptedData, SecretKey key) async {
    if (encryptedData.length < 28) throw Exception('Invalid encrypted data');

    final nonce = encryptedData.sublist(0, 12);
    final tag = encryptedData.sublist(12, 28);
    final ciphertext = encryptedData.sublist(28);

    final secretBox = SecretBox(
      ciphertext,
      nonce: nonce,
      mac: Mac(tag),
    );

    final cleartext = await _cipher.decrypt(
      secretBox,
      secretKey: key,
    );
    return Uint8List.fromList(cleartext);
  }

  /// Encrypts a password using RSA Public Key (for sending to server).
  static String encryptPassword(String password, String publicKeyPem) {
    final publicKey = enc.RSAKeyParser().parse(publicKeyPem);
    final encrypter = enc.Encrypter(enc.RSA(
      publicKey: publicKey as pc.RSAPublicKey,
      encoding: enc.RSAEncoding.OAEP,
    ));
    final encrypted = encrypter.encrypt(password);
    return encrypted.base64;
  }

  /// Generates a random 32-byte AES session key as a hex string.
  static String generateSessionKey() {
    final key = enc.Key.fromSecureRandom(32);
    return key.bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  /// Encrypts the hex session key using RSA Public Key.
  static String encryptSessionKey(String sessionKeyHex, String publicKeyPem) {
    final publicKey = enc.RSAKeyParser().parse(publicKeyPem);
    final encrypter = enc.Encrypter(enc.RSA(
      publicKey: publicKey as pc.RSAPublicKey,
      encoding: enc.RSAEncoding.OAEP,
    ));
    final encrypted = encrypter.encrypt(sessionKeyHex);
    return encrypted.base64;
  }

  /// Decrypts a server response (IV + Tag + Ciphertext) using the hex session key.
  static Future<String> decryptResponse(String encryptedBase64, String sessionKeyHex) async {
    final blob = base64.decode(encryptedBase64);
    if (blob.length < 32) throw Exception('Invalid encrypted response');

    final iv = blob.sublist(0, 16);
    final tag = blob.sublist(16, 32);
    final ciphertext = blob.sublist(32);

    final secretKey = SecretKey(Uint8List.fromList(
      Iterable.generate(32, (i) => int.parse(sessionKeyHex.substring(i * 2, i * 2 + 2), radix: 16)).toList()
    ));

    final secretBox = SecretBox(
      ciphertext,
      nonce: iv,
      mac: Mac(tag),
    );

    final cleartext = await _cipher.decrypt(
      secretBox,
      secretKey: secretKey,
    );
    return utf8.decode(cleartext);
  }

  /// Computes HMAC-SHA256.
  static Future<Uint8List> generateHmac(Uint8List data, String password) async {
    final hmac = Hmac.sha256();
    final mac = await hmac.calculateMac(
      data,
      secretKey: SecretKey(utf8.encode(password)),
    );
    return Uint8List.fromList(mac.bytes);
  }
}
