import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'logging.dart';

class ApiException implements Exception {
  const ApiException(this.code, {this.status});
  final String code;
  final int? status;
}

class ApiClient {
  ApiClient(this.baseUrl, this.client, {this.accessToken});
  final String baseUrl;
  final http.Client client;
  final Future<String?> Function()? accessToken;
  String? csrfToken;
  Future<Map<String, dynamic>> request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = false,
  }) async {
    if (!path.startsWith('/') || path.startsWith('//') || path.contains('..')) {
      throw const ApiException('invalid_path');
    }
    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers['Content-Type'] = 'application/json';
    if (authenticated) {
      final token = await accessToken?.call();
      if (token != null) request.headers['Authorization'] = 'Bearer $token';
      if (csrfToken != null) request.headers['X-CSRF-Token'] = csrfToken!;
    }
    if (body != null) request.body = jsonEncode(body);
    try {
      final response = await http.Response.fromStream(
        await client.send(request),
      ).timeout(const Duration(seconds: 15));
      final decoded = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        throw ApiException(
          decoded['error']?['code'] as String? ?? 'request_failed',
          status: response.statusCode,
        );
      }
      return decoded;
    } on ApiException {
      rethrow;
    } on Object {
      AppLog.requestFailed();
      throw const ApiException('connection_failed');
    }
  }

  Future<Map<String, dynamic>> health() => request('GET', '/health');
}
