import 'dart:typed_data';
import '../core/api_client.dart';

/// Test-harness adapter only. No app provider, route, picker or persistence.
/// All images are controlled synthetic fixtures; the server enforces the allowlist.
class SyntheticUploadService {
  SyntheticUploadService(this.api);
  final ApiClient api;
  int _generation = 0;
  Uint8List? _pending;
  bool get hasPendingBytes => _pending != null;

  /// Call before logout/disposal. A disconnected client cannot promise remote purge.
  void clearSession() {
    _generation++;
    _pending?.fillRange(0, _pending!.length, 0);
    _pending = null;
  }

  String _path(String id) {
    if (!RegExp(
      r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$',
    ).hasMatch(id)) {
      throw const ApiException('invalid_upload_id');
    }
    return '/uploads/$id';
  }

  void _current(int generation) {
    if (generation != _generation) throw const ApiException('upload_cancelled');
  }

  Future<Map<String, dynamic>> upload({
    required Uint8List fixture,
    required String checksum,
    required String requestKey,
    String documentKind = 'box',
    bool retainForReview = false,
  }) async {
    if (_pending != null) throw const ApiException('upload_in_progress');
    if (fixture.isEmpty ||
        fixture.length > 10485760 ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(checksum)) {
      throw const ApiException('invalid_fixture');
    }
    final generation = _generation;
    final data = Uint8List.fromList(fixture);
    _pending = data;
    try {
      final intent = await api.request(
        'POST',
        '/uploads',
        authenticated: true,
        headers: {'Idempotency-Key': requestKey},
        body: {
          'content_type': 'image/png',
          'byte_size': data.length,
          'document_kind': documentKind,
          'consent_version': 'synthetic-v1',
          'retain_for_review': retainForReview,
          'checksum_sha256': checksum,
        },
      );
      _current(generation);
      final path = _path(intent['upload_id'] as String);
      final ticket = intent['ticket'] as String?;
      if (ticket == null) throw const ApiException('ticket_unavailable');
      // Construct the same-origin path; never follow a server-supplied upload URL.
      await api.request(
        'PUT',
        '$path/content',
        authenticated: true,
        headers: {'X-Upload-Ticket': ticket},
        bytes: data,
        contentType: 'image/png',
      );
      _current(generation);
      final current = await status(intent['upload_id'] as String);
      _current(generation);
      final result = await api.request(
        'POST',
        '$path/complete',
        authenticated: true,
        headers: {
          'Idempotency-Key': requestKey,
          'If-Match': '"${current['version']}"',
        },
        body: {'checksum_sha256': checksum},
      );
      _current(generation);
      return result;
    } finally {
      data.fillRange(0, data.length, 0);
      if (identical(_pending, data)) _pending = null;
    }
  }

  Future<Map<String, dynamic>> status(String id) =>
      api.request('GET', _path(id), authenticated: true);

  Future<Map<String, dynamic>> delete(String id, int version) {
    clearSession();
    return api.request(
      'DELETE',
      _path(id),
      authenticated: true,
      headers: {'If-Match': '"$version"'},
    );
  }

  Future<Map<String, dynamic>> receipts(String id) =>
      api.request('GET', '${_path(id)}/receipts', authenticated: true);

  Future<Uint8List> preview(String id) async {
    final generation = _generation;
    final data = await api.previewBytes('${_path(id)}/preview');
    if (generation != _generation) {
      data.fillRange(0, data.length, 0);
      throw const ApiException('upload_cancelled');
    }
    return data; // Caller owns the short-lived bytes; never written to disk/cache.
  }
}
