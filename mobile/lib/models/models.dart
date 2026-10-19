/// B17 فاز ۳۶ — مدل‌های سبک کلاینت موبایل.
///
/// فقط فیلدهای لازم برای نمایش؛ هیچ داده بالینی روی دستگاه نگه داشته
/// نمی‌شود و مدل‌ها فقط در حافظه نشست جاری زندگی می‌کنند.
library;

class MyProfile {
  const MyProfile({
    required this.displayName,
    required this.nationalId,
    required this.mobile,
    required this.unitTitle,
  });

  final String displayName;
  final String? nationalId;
  final String? mobile;
  final String? unitTitle;

  factory MyProfile.fromMap(Map<String, dynamic> m) {
    final first = (m['first_name'] ?? '') as String;
    final last = (m['last_name'] ?? '') as String;
    return MyProfile(
      displayName: ('$first $last').trim(),
      nationalId: m['national_id'] as String?,
      mobile: m['mobile'] as String?,
      unitTitle: m['unit_title'] as String?,
    );
  }
}

class MyAppointment {
  const MyAppointment({
    required this.id,
    required this.caseNumber,
    required this.scheduledAt,
    required this.status,
    required this.location,
  });

  final String id;
  final String caseNumber;
  final String scheduledAt;
  final String status;
  final String? location;

  factory MyAppointment.fromMap(Map<String, dynamic> m) => MyAppointment(
        id: m['id'] as String,
        caseNumber: (m['case_number'] ?? '') as String,
        scheduledAt: (m['scheduled_at'] ?? '') as String,
        status: (m['status'] ?? '') as String,
        location: m['location'] as String?,
      );
}

class AppNotification {
  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.severity,
    required this.readAt,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String? body;
  final String severity;
  final String? readAt;
  final String? createdAt;

  bool get isRead => readAt != null;

  factory AppNotification.fromMap(Map<String, dynamic> m) => AppNotification(
        id: m['id'] as String,
        title: (m['title'] ?? '') as String,
        body: m['body'] as String?,
        severity: (m['severity'] ?? 'info') as String,
        readAt: m['read_at'] as String?,
        createdAt: m['created_at'] as String?,
      );
}

class MyOrder {
  const MyOrder({
    required this.id,
    required this.orderNumber,
    required this.title,
    required this.payableAmount,
    required this.status,
  });

  final String id;
  final String orderNumber;
  final String title;
  final num payableAmount;
  final String status;

  factory MyOrder.fromMap(Map<String, dynamic> m) => MyOrder(
        id: m['id'] as String,
        orderNumber: (m['order_number'] ?? '') as String,
        title: (m['title'] ?? '') as String,
        payableAmount: (m['payable_amount'] ?? 0) as num,
        status: (m['status'] ?? '') as String,
      );
}
