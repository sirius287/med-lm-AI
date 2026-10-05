import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
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
    Map<String, String> headers = const {},
    Uint8List? bytes,
    String contentType = 'application/json',
  }) async {
    if (!path.startsWith('/') || path.startsWith('//') || path.contains('..')) {
      throw const ApiException('invalid_path');
    }
    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers['Content-Type'] = 'application/json';
    if (headers.keys.any(
      (key) => !const {
        'Idempotency-Key',
        'If-Match',
        'X-Upload-Ticket',
      }.contains(key),
    )) {
      throw const ApiException('invalid_headers');
    }
    request.headers.addAll(headers);
    request.headers['Content-Type'] = contentType;
    request.followRedirects = false;
    if (authenticated) {
      final token = await accessToken?.call();
      if (token != null) request.headers['Authorization'] = 'Bearer $token';
      if (csrfToken != null) request.headers['X-CSRF-Token'] = csrfToken!;
    }
    if (body != null) request.body = jsonEncode(body);
    if (bytes != null) request.bodyBytes = bytes;
    try {
      final response = await http.Response.fromStream(
        await client.send(request),
      ).timeout(const Duration(seconds: 15));
      if (response.statusCode >= 300 && response.statusCode < 400) {
        throw const ApiException('redirect_denied');
      }
      if (response.statusCode == 401) csrfToken = null;
      final decoded = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        if (response.statusCode == 401) csrfToken = null;
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

  Future<Uint8List> previewBytes(String path) async {
    if (!RegExp(r'^/uploads/[0-9a-fA-F-]{36}/preview$').hasMatch(path)) {
      throw const ApiException('invalid_path');
    }
    Future<Uint8List> read() async {
      final request = http.Request('GET', Uri.parse('$baseUrl$path'))
        ..followRedirects = false;
      final token = await accessToken?.call();
      if (token != null) request.headers['Authorization'] = 'Bearer $token';
      final response = await client.send(request);
      if (response.statusCode == 401) csrfToken = null;
      if (response.statusCode != 200) {
        throw ApiException('preview_unavailable', status: response.statusCode);
      }
      if (response.headers['content-type'] != 'image/png' ||
          response.headers['cache-control'] != 'no-store') {
        throw const ApiException('invalid_preview');
      }
      final result = BytesBuilder(copy: false);
      await for (final chunk in response.stream) {
        if (result.length + chunk.length > 10485760) {
          throw const ApiException('image_size');
        }
        result.add(chunk);
      }
      return result.takeBytes();
    }

    try {
      return await read().timeout(const Duration(seconds: 15));
    } on ApiException {
      rethrow;
    } on Object {
      throw const ApiException('connection_failed');
    }
  }
}
