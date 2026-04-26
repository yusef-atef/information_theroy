import 'dart:io';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:googleapis/drive/v3.dart' as drive;
import 'package:extension_google_sign_in_as_googleapis_auth/extension_google_sign_in_as_googleapis_auth.dart';
import 'package:http/http.dart' as http;

class GoogleDriveService {
  static final GoogleDriveService instance = GoogleDriveService._();
  GoogleDriveService._();

  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: [
      drive.DriveApi.driveAppdataScope,
    ],
  );

  GoogleSignInAccount? _user;
  drive.DriveApi? _driveApi;

  Future<bool> signIn() async {
    try {
      _user = await _googleSignIn.signIn();
      if (_user == null) {
        print('Google Drive: Sign-in was cancelled by user or config error.');
        return false;
      }

      final httpClient = (await _googleSignIn.authenticatedClient());
      if (httpClient == null) {
        print('Google Drive: Failed to get authenticated HTTP client.');
        return false;
      }
      
      _driveApi = drive.DriveApi(httpClient);
      print('Google Drive: Sign-in successful for ${_user?.email}');
      return true;
    } catch (e) {
      print('Google Sign-In Exception: $e');
      rethrow; 
    }
  }

  Future<void> signOut() async {
    await _googleSignIn.signOut();
    _user = null;
    _driveApi = null;
  }

  bool get isSignedIn => _user != null;

  /// Ensures the user is signed in and the HTTP client is fresh.
  Future<void> _ensureAuthenticated() async {
    // Try to sign in silently first to refresh tokens
    _user = await _googleSignIn.signInSilently();
    if (_user == null) {
      // If silent fails, try full sign in
      _user = await _googleSignIn.signIn();
    }
    
    if (_user == null) throw Exception('Google Drive authentication failed');

    final httpClient = await _googleSignIn.authenticatedClient();
    if (httpClient == null) throw Exception('Failed to get authenticated HTTP client');
    
    _driveApi = drive.DriveApi(httpClient);
  }

  /// Uploads a file to the hidden AppData folder on Google Drive.
  /// Returns the Google File ID.
  Future<String?> uploadFile(File file, String filename) async {
    await _ensureAuthenticated();

    final driveFile = drive.File();
    driveFile.name = filename;
    driveFile.parents = ['appDataFolder'];

    final media = drive.Media(file.openRead(), file.lengthSync());
    final result = await _driveApi!.files.create(driveFile, uploadMedia: media);
    return result.id;
  }

  /// Downloads a file from Google Drive as a list of bytes.
  Future<List<int>> downloadFile(String fileId) async {
    await _ensureAuthenticated();

    final media = await _driveApi!.files.get(fileId, downloadOptions: drive.DownloadOptions.fullMedia) as drive.Media;
    final List<int> data = [];
    await for (final chunk in media.stream) {
      data.addAll(chunk);
    }
    return data;
  }

  /// Deletes a file from Google Drive.
  Future<void> deleteFile(String fileId) async {
    await _ensureAuthenticated();
    await _driveApi!.files.delete(fileId);
  }
}
