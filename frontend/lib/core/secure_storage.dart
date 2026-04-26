import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
  iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
);

class SecureStorage {
  SecureStorage._();

  static const _keyAccess = 'sc_access_token';
  static const _keyRefresh = 'sc_refresh_token';
  static const _keyUsername = 'sc_username';
  static const _keyPassword = 'sc_password';

  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await Future.wait([
      _storage.write(key: _keyAccess, value: accessToken),
      _storage.write(key: _keyRefresh, value: refreshToken),
    ]);
  }

  static Future<String?> getAccessToken() => _storage.read(key: _keyAccess);
  static Future<String?> getRefreshToken() => _storage.read(key: _keyRefresh);

  static Future<void> saveUsername(String username) =>
      _storage.write(key: _keyUsername, value: username);
  static Future<String?> getUsername() => _storage.read(key: _keyUsername);

  static Future<void> savePassword(String password) =>
      _storage.write(key: _keyPassword, value: password);
  static Future<String?> getPassword() => _storage.read(key: _keyPassword);

  static Future<bool> isLoggedIn() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  static Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
