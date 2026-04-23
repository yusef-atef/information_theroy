import 'dart:io';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'secure_storage.dart';

const String _baseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000', // Android emulator → localhost
);

class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  late final Dio _dio = Dio(BaseOptions(
    baseUrl: _baseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ))
    ..interceptors.add(_AuthInterceptor())
    ..interceptors.add(LogInterceptor(requestBody: false, responseBody: false));

  Dio get dio {
    // For development: Bypass SSL pinning / certificate validation
    if (_dio.httpClientAdapter is IOHttpClientAdapter) {
      (_dio.httpClientAdapter as IOHttpClientAdapter).createHttpClient = () {
        final client = HttpClient();
        client.badCertificateCallback = (cert, host, port) => true;
        return client;
      };
    }
    return _dio;
  }
}

// ---------------------------------------------------------------------------
// Auth interceptor — attaches JWT, refreshes on 401
// ---------------------------------------------------------------------------

class _AuthInterceptor extends Interceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await SecureStorage.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    return handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode == 401) {
      // Attempt token refresh
      final refreshToken = await SecureStorage.getRefreshToken();
      if (refreshToken != null) {
        try {
          final response = await ApiClient.instance.dio.post(
            '/auth/refresh',
            options: Options(headers: {'Authorization': 'Bearer $refreshToken'}),
          );
          final newAccess = response.data['access_token'] as String;
          final newRefresh = response.data['refresh_token'] as String;
          await SecureStorage.saveTokens(
            accessToken: newAccess,
            refreshToken: newRefresh,
          );
          // Retry original request
          final opts = err.requestOptions;
          opts.headers['Authorization'] = 'Bearer $newAccess';
          final retried = await ApiClient.instance.dio.fetch(opts);
          return handler.resolve(retried);
        } catch (_) {
          await SecureStorage.clearAll();
        }
      }
    }
    return handler.next(err);
  }
}

// ---------------------------------------------------------------------------
// Typed API methods
// ---------------------------------------------------------------------------

extension AuthApi on Dio {
  Future<Map<String, dynamic>> register({
    required String username,
    required String email,
    required String password,
  }) async {
    final res = await post('/auth/register', data: {
      'username': username,
      'email': email,
      'password': password,
    });
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    final res = await post('/auth/login', data: {
      'username': username,
      'password': password,
    });
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getMe() async {
    final res = await get('/auth/me');
    return res.data as Map<String, dynamic>;
  }

  Future<List<dynamic>> listFiles() async {
    final res = await get('/files/list');
    return (res.data as Map<String, dynamic>)['files'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> uploadFile(String filePath, String filename) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath, filename: filename),
    });
    final res = await post('/files/upload', data: formData,
        options: Options(contentType: 'multipart/form-data'));
    return res.data as Map<String, dynamic>;
  }

  Future<List<int>> downloadFile(String fileId) async {
    final res = await get(
      '/files/download/$fileId',
      options: Options(responseType: ResponseType.bytes),
    );
    return res.data as List<int>;
  }

  Future<void> deleteFile(String fileId) async {
    await delete('/files/$fileId');
  }
}
