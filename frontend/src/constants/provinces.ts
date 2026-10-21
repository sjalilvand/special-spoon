// فاز ۴۹: استان‌های ایران (۳۱ استان) با مرکز استان و موقعیت پیش‌فرض
// — برای ثبت سریع شعبه: انتخاب استان، شهر و مختصات را خودکار پر می‌کند.
export interface ProvinceInfo {
  name: string;
  capital: string;
  lat: number;
  lng: number;
  area_code: string;
}

export const IRAN_PROVINCES: ProvinceInfo[] = [
  { name: "آذربایجان شرقی", capital: "تبریز", lat: 38.0962, lng: 46.2738, area_code: "041" },
  { name: "آذربایجان غربی", capital: "ارومیه", lat: 37.5527, lng: 45.0759, area_code: "044" },
  { name: "اردبیل", capital: "اردبیل", lat: 38.2498, lng: 48.2933, area_code: "045" },
  { name: "اصفهان", capital: "اصفهان", lat: 32.6539, lng: 51.6660, area_code: "031" },
  { name: "البرز", capital: "کرج", lat: 35.8355, lng: 50.9915, area_code: "026" },
  { name: "ایلام", capital: "ایلام", lat: 33.6374, lng: 46.4227, area_code: "084" },
  { name: "بوشهر", capital: "بوشهر", lat: 28.9234, lng: 50.8203, area_code: "077" },
  { name: "تهران", capital: "تهران", lat: 35.6892, lng: 51.3890, area_code: "021" },
  { name: "چهارمحال و بختیاری", capital: "شهرکرد", lat: 32.3256, lng: 50.8644, area_code: "038" },
  { name: "خراسان جنوبی", capital: "بیرجند", lat: 32.8663, lng: 59.2211, area_code: "056" },
  { name: "خراسان رضوی", capital: "مشهد", lat: 36.2605, lng: 59.6168, area_code: "051" },
  { name: "خراسان شمالی", capital: "بجنورد", lat: 37.4747, lng: 57.3290, area_code: "058" },
  { name: "خوزستان", capital: "اهواز", lat: 31.3183, lng: 48.6706, area_code: "061" },
  { name: "زنجان", capital: "زنجان", lat: 36.6736, lng: 48.4787, area_code: "024" },
  { name: "سمنان", capital: "سمنان", lat: 35.5729, lng: 53.3970, area_code: "023" },
  { name: "سیستان و بلوچستان", capital: "زاهدان", lat: 29.4963, lng: 60.8629, area_code: "054" },
  { name: "فارس", capital: "شیراز", lat: 29.5918, lng: 52.5837, area_code: "071" },
  { name: "قزوین", capital: "قزوین", lat: 36.2797, lng: 50.0049, area_code: "028" },
  { name: "قم", capital: "قم", lat: 34.6416, lng: 50.8746, area_code: "025" },
  { name: "کردستان", capital: "سنندج", lat: 35.3219, lng: 46.9862, area_code: "087" },
  { name: "کرمان", capital: "کرمان", lat: 30.2839, lng: 57.0834, area_code: "034" },
  { name: "کرمانشاه", capital: "کرمانشاه", lat: 34.3142, lng: 47.0650, area_code: "083" },
  { name: "کهگیلویه و بویراحمد", capital: "یاسوج", lat: 30.6684, lng: 51.5879, area_code: "074" },
  { name: "گلستان", capital: "گرگان", lat: 36.8456, lng: 54.4393, area_code: "017" },
  { name: "گیلان", capital: "رشت", lat: 37.2808, lng: 49.5832, area_code: "013" },
  { name: "لرستان", capital: "خرم‌آباد", lat: 33.4878, lng: 48.3558, area_code: "066" },
  { name: "مازندران", capital: "ساری", lat: 36.5633, lng: 53.0601, area_code: "011" },
  { name: "مرکزی", capital: "اراک", lat: 34.0917, lng: 49.6892, area_code: "086" },
  { name: "هرمزگان", capital: "بندرعباس", lat: 27.1865, lng: 56.2808, area_code: "076" },
  { name: "همدان", capital: "همدان", lat: 34.7983, lng: 48.5148, area_code: "081" },
  { name: "یزد", capital: "یزد", lat: 31.8974, lng: 54.3569, area_code: "035" },
];

export const findProvince = (name: string | null | undefined): ProvinceInfo | undefined =>
  IRAN_PROVINCES.find((p) => p.name === name);
