/// B17 فاز ۳۶ — کلاینت REST سامانه Rosepsy.
///
/// فاز ۴۰ — گام ۳ طرح مهاجرت ADR-03: اپ موبایل مستقیماً روی `/api/v2`
/// (بدون گذر از v1) و پاسخ‌خوانی پاکت استاندارد سند:
///
/// ```jsonc
/// // موفقیت: payload در «data»، متادیتا در «meta»
/// { "data": <payload>, "meta": { "request_id", "timestamp", "version", "duration_ms" }, "errors": null }
/// // خطا: کد پایدار + پیام فارسی در «errors»
/// { "data": null, "meta": { ... }, "errors": [ { "code", "message" } ] }
/// ```
///
/// قواعد سند که در این لایه رعایت می‌شود:
/// - توکن دسترسی در هدر Authorization Bearer ارسال می‌شود؛
/// - نشست منقضی (401) → AuthException و خروج به صفحه ورود؛
/// - پیام خطای فارسی سرور (errors[0].message) بدون تغییر به کاربر نشان داده می‌شود؛
/// - `request_id` هر پاسخ در `lastMeta` نگه داشته می‌شود (ردیابی پشتیبانی فنی B23)؛
/// - هیچ پاسخی روی دیسک کش نمی‌شود (بدون داده بالینی روی دستگاه).
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

/// آدرس پایه API — هنگام build با dart-define تنظیم می‌شود:
/// flutter run --dart-define=ROSEPSY_API_BASE=https://clinic.example.ir/api/v2
const String kApiBase = String.fromEnvironment(
  'ROSEPSY_API_BASE',
  defaultValue: 'http://10.0.2.2:8080/api/v2',
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

  /// متادیتای آخرین پاسخ (request_id/timestamp/...) — فقط برای ردیابی.
  Map<String, dynamic>? lastMeta;

  bool get hasToken => _accessToken != null;

  void setToken(String? token) {
    _accessToken = (token == null || token.isEmpty) ? null : token;
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_accessToken != null) 'Authorization': 'Bearer $_accessToken',
      };

  /// GET و برگرداندن payload واقعی (محتوای «data» پاکت v2).
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

  /// نقطه واحد سازگاری با پاکت v2 — همان رویکرد مهاجرت فرانت‌اند (0.39.0).
  ///
  /// - پاسخ پاکت‌دار: payload واقعی از «data» برمی‌گردد و «meta» در [lastMeta] می‌ماند؛
  /// - پیام خطا از `errors[0].message` خوانده می‌شود (fallback به `detail` برای
  ///   سازگاری با پاسخ‌های خام v1 در صورت تنظیم دستی پایه قدیمی)؛
  /// - بدنه غیر-پاکتی (بدون «data» و «meta») به‌عنوان payload خام عبور می‌کند.
  Map<String, dynamic> _handle(http.Response res) {
    Map<String, dynamic> body;
    try {
      final decoded = jsonDecode(utf8.decode(res.bodyBytes));
      body = decoded is Map<String, dynamic> ? decoded : const {};
    } catch (_) {
      body = const {};
    }

    final bool isEnvelope = body.containsKey('meta') || body.containsKey('errors');
    String? serverMessage;
    if (isEnvelope) {
      final errs = body['errors'];
      if (errs is List && errs.isNotEmpty && errs.first is Map) {
        final m = errs.first['message'];
        if (m is String && m.isNotEmpty) serverMessage = m;
      }
      lastMeta = body['meta'] is Map<String, dynamic>
          ? body['meta'] as Map<String, dynamic>
          : null;
    } else {
      final detail = body['detail'];
      if (detail is String && detail.isNotEmpty) serverMessage = detail;
      lastMeta = null;
    }

    if (res.statusCode == 401) {
      throw AuthException(serverMessage ?? 'نشست منقضی شده است؛ دوباره وارد شوید');
    }
    if (res.statusCode >= 400) {
      throw ApiException(
        res.statusCode,
        serverMessage ?? 'خطای نامشخص رخ داد (${res.statusCode})',
      );
    }

    // payload واقعی — در پاکت v2 از «data»، در بدنه خام خود بدنه
    if (isEnvelope) {
      final data = body['data'];
      return data is Map<String, dynamic> ? data : const {};
    }
    return body;
  }

  void close() => _client.close();
}
