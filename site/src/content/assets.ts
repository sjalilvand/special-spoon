// تولید خودکار توسط اسکریپت ۲۶ — برای بازتولید، اسکریپت را دوباره اجرا کنید
export interface SiteAsset {
  file: string;
  original: string;
}

export const IMAGES: SiteAsset[] = [
   { file: "/assets/img-1.webp", original: "location-150x150-1-20x20.webp" },
  { file: "/assets/img-2.webp", original: "mail-20x20.webp" },
  { file: "/assets/img-3.png", original: "rose-logo-1-300x65.png" },
  { file: "/assets/img-4.png", original: "rose-logo-1.png" },
  { file: "/assets/img-5.png", original: "rose-logo-2.png" },
  { file: "/assets/img-6.webp", original: "tell-04-20x20.webp" },
  { file: "/assets/img-7.png", original: "vr-14-1-150x150.png" },
  { file: "/assets/img-8.png", original: "vr-14-1-300x256.png" },
  { file: "/assets/img-9.svg", original: "آموزش-1.svg" },
  { file: "/assets/img-10.png", original: "آیکن-رز_نوروفیدبک-1-300x287.png" },
  { file: "/assets/img-11.png", original: "بنرسایت-17-17-17-1.png" },
  { file: "/assets/img-12.png", original: "بنرسایت-24-30-3.png" },
  { file: "/assets/img-13.png", original: "بنرسایت-27-1.png" },
  { file: "/assets/img-14.png", original: "بنرسایت-28-1.png" },
  { file: "/assets/img-15.svg", original: "بنرسایت-29.svg" },
  { file: "/assets/img-16.webp", original: "رضایت-WEB.webp" },
  { file: "/assets/img-17.png", original: "رضایت-مشتری-18.png" },
  { file: "/assets/img-18.jpg", original: "رضایت-مشتری-19-300x300.jpg" },
  { file: "/assets/img-19.jpg", original: "رضایت-مشتری-20-300x300.jpg" },
  { file: "/assets/img-20.svg", original: "روان-درمانی.svg" },
  { file: "/assets/img-21.svg", original: "زوج.svg" },
  { file: "/assets/img-22.svg", original: "زوج(1).svg" },
  { file: "/assets/img-23.svg", original: "کودک-و-نوجوان.svg" },
  { file: "/assets/img-24.svg", original: "کودک-و-نوجوان(1).svg" },
  { file: "/assets/img-25.svg", original: "مایند-مپ.svg" },
  { file: "/assets/img-26.svg", original: "مشاوره-1.svg" },
  { file: "/assets/img-27.svg", original: "مشاوره-انفرادی.svg" },
  { file: "/assets/img-28.svg", original: "مشاوره-گروهی.svg" },
  { file: "/assets/img-29.svg", original: "مشاوره-گروهی(1).svg" },
];

export const SUGGESTED: {
  logo: string | null;
  hero: string[];
  icons: string[];
  about: string | null;
  counselors: string[];
} = {
  logo: "/assets/img-3.png",
  hero: ["/assets/img-11.png", "/assets/img-12.png", "/assets/img-13.png"],
  icons: ["/assets/img-9.svg", "/assets/img-15.svg", "/assets/img-20.svg", "/assets/img-21.svg", "/assets/img-22.svg", "/assets/img-23.svg", "/assets/img-24.svg", "/assets/img-25.svg"],
  about: null,
  counselors: ["/assets/img-26.svg", "/assets/img-27.svg", "/assets/img-28.svg", "/assets/img-29.svg"],
};
