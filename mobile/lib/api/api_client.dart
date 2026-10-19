/// B17 فاز ۳۶ — کلاینت REST سامانه Rosepsy.
///
/// قواعد سند که در این لایه رعایت می‌شود:
/// - توکن دسترسی در هدر Authorization Bearer ارسال می‌شود؛
/// - نشست منقضی (401) → AuthException و خروج به صفحه ورود؛
/// - پیام خطای فارسی سرور (detail) بدون تغییر به کاربر نشان داده می‌شود؛
/// - هیچ پاسخی روی دیسک کش نمی‌شود (بدون داده بالینی روی دستگاه).
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

/// آدرس پایه API — هنگام build با dart-define تنظیم می‌شود:
/// flutter run --dart-define=ROSEPSY_API_BASE=https://clinic.example.ir/api/v1
const String kApiBase = String.fromEnvironment(
  'ROSEPSY_API_BASE',
  defaultValue: 'http://10.0.2.2:8080/api/v1',
);

/// خطای نشست — مصرف‌کننده باید کاربر را به صفحه ورود برگرداند.
class AuthException implements Exception {
  final String message;
  const AuthException(this.message);
  @override
  String toString() => message;
}

/// خطای عمومی API با پیام فارسی سرور.
class ApiException implements Exception {
  final int status;
  final String detail;
  const ApiException(this.status, this.detail);
  @override
  String toString() => detail;
}

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  String? _accessToken;

  bool get hasToken => _accessToken != null;

  void setToken(String? token) {
    _accessToken = (token == null || token.isEmpty) ? null : token;
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_accessToken != null) 'Authorization': 'Bearer $_accessToken',
      };

  /// GET و برگرداندن JSON دیکشنری.
  Future<Map<String, dynamic>> get(String path) async {
    final res = await _client.get(
      Uri.parse('$kApiBase$path'),
      headers: _headers,
    );
    return _handle(res);
  }

  /// POST با بدنه JSON.
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final res = await _client.post(
      Uri.parse('$kApiBase$path'),
      headers: _headers,
      body: jsonEncode(body ?? const {}),
    );
    return _handle(res);
  }

  Map<String, dynamic> _handle(http.Response res) {
    Map<String, dynamic> data;
    try {
      final decoded = jsonDecode(utf8.decode(res.bodyBytes));
      data = decoded is Map<String, dynamic> ? decoded : const {};
    } catch (_) {
      data = const {};
    }
    if (res.statusCode == 401) {
      throw AuthException(
        data['detail'] is String
            ? data['detail'] as String
            : 'نشست منقضی شده است؛ دوباره وارد شوید',
      );
    }
    if (res.statusCode >= 400) {
      final detail = data['detail'];
      throw ApiException(
        res.statusCode,
        detail is String ? detail : 'خطای نامشخص رخ داد (${res.statusCode})',
      );
    }
    return data;
  }

  void close() => _client.close();
}
