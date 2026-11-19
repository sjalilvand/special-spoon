// فاز ۹۸ — آیکون اختصاصی هر آزمون در کاتالوگ و اجرا (slug → MUI icon)
// بر اساس موضوع و سازوکار آزمون؛ آزمون‌های ناشناخته به آیکونِ دستهٔ موضوعی می‌روند.
import PersonRounded from "@mui/icons-material/PersonRounded";
import GroupsRounded from "@mui/icons-material/GroupsRounded";
import WorkRounded from "@mui/icons-material/WorkRounded";
import PsychologyRounded from "@mui/icons-material/PsychologyRounded";
import LightbulbRounded from "@mui/icons-material/LightbulbRounded";
import SchoolRounded from "@mui/icons-material/SchoolRounded";
import SpaRounded from "@mui/icons-material/SpaRounded";
import HealthAndSafetyRounded from "@mui/icons-material/HealthAndSafetyRounded";
import MoodBadRounded from "@mui/icons-material/MoodBadRounded";
import MonitorHeartRounded from "@mui/icons-material/MonitorHeartRounded";
import AnalyticsRounded from "@mui/icons-material/AnalyticsRounded";
import SentimentNeutralRounded from "@mui/icons-material/SentimentNeutralRounded";
import CloudRounded from "@mui/icons-material/CloudRounded";
import SpeedRounded from "@mui/icons-material/SpeedRounded";
import WorkspacePremiumRounded from "@mui/icons-material/WorkspacePremiumRounded";
import FavoriteRounded from "@mui/icons-material/FavoriteRounded";
import EmojiEmotionsRounded from "@mui/icons-material/EmojiEmotionsRounded";
import PersonSearchRounded from "@mui/icons-material/PersonSearchRounded";
import ViewModuleRounded from "@mui/icons-material/ViewModuleRounded";
import BalanceRounded from "@mui/icons-material/BalanceRounded";
import SchemaRounded from "@mui/icons-material/SchemaRounded";
import VolunteerActivismRounded from "@mui/icons-material/VolunteerActivismRounded";
import RecordVoiceOverRounded from "@mui/icons-material/RecordVoiceOverRounded";
import EmojiObjectsRounded from "@mui/icons-material/EmojiObjectsRounded";
import BusinessCenterRounded from "@mui/icons-material/BusinessCenterRounded";
import TipsAndUpdatesRounded from "@mui/icons-material/TipsAndUpdatesRounded";
import ExploreRounded from "@mui/icons-material/ExploreRounded";
import DrawRounded from "@mui/icons-material/DrawRounded";
import ExtensionRounded from "@mui/icons-material/ExtensionRounded";
import WidgetsRounded from "@mui/icons-material/WidgetsRounded";
import WaterDropRounded from "@mui/icons-material/WaterDropRounded";
import AutoAwesomeRounded from "@mui/icons-material/AutoAwesomeRounded";
import AnchorRounded from "@mui/icons-material/AnchorRounded";
import LocalHospitalRounded from "@mui/icons-material/LocalHospitalRounded";
import LocalFireDepartmentRounded from "@mui/icons-material/LocalFireDepartmentRounded";
import WhatshotRounded from "@mui/icons-material/WhatshotRounded";
import EmojiEventsRounded from "@mui/icons-material/EmojiEventsRounded";
import PeopleRounded from "@mui/icons-material/PeopleRounded";
import QuizRounded from "@mui/icons-material/QuizRounded";
import SelfImprovementRounded from "@mui/icons-material/SelfImprovementRounded";
import StarsRounded from "@mui/icons-material/StarsRounded";
import GrainRounded from "@mui/icons-material/GrainRounded";
import type { ComponentType, SvgIconProps } from "@mui/material/SvgIcon";

type IconType = ComponentType<SvgIconProps>;

const BY_SLUG: Record<string, IconType> = {
  "bdi-ii": MoodBadRounded,
  "bai": MonitorHeartRounded,
  "dass-21": AnalyticsRounded,
  "phq-9": SentimentNeutralRounded,
  "gad-7": CloudRounded,
  "pss-10": SpeedRounded,
  "ghq-12": HealthAndSafetyRounded,
  "ghq-28": HealthAndSafetyRounded,
  "rosenberg": WorkspacePremiumRounded,
  "mes-20": FavoriteRounded,
  "mes-40": FavoriteRounded,
  "eq-24": EmojiEmotionsRounded,
  "gardner-mit": LightbulbRounded,
  "gardner-mit-80": AutoAwesomeRounded,
  "mmpi-sf-370": PsychologyRounded,
  "mcmi-iii-175": PersonSearchRounded,
  "cattell-16pf-187": ViewModuleRounded,
  "mbti-88": BalanceRounded,
  "neo-pi-r": SchemaRounded,
  "baron-eq-i-90": VolunteerActivismRounded,
  "shering-eq-33": RecordVoiceOverRounded,
  "schutte-mseis-41": EmojiObjectsRounded,
  "minnesota-msq-19": WorkRounded,
  "osipow-osi-60": BusinessCenterRounded,
  "jazani-jcq-37": TipsAndUpdatesRounded,
  "holland-hcq-60": ExploreRounded,
  "torrance-ttct-60": DrawRounded,
  "raven-cpm-36": ExtensionRounded,
  "raven-rspm-60": WidgetsRounded,
  "glasser-bnq": WaterDropRounded,
  "schein-anchors": AnchorRounded,
  "scl-90-r": LocalHospitalRounded,
  "maslach-mbi": LocalFireDepartmentRounded,
  "bass-perry": WhatshotRounded,
  "sherer-gse": EmojiEventsRounded,
  "hazen-shaver": PeopleRounded,
  "ahvaz-ta": QuizRounded,
  "whoqol-bref": SpaRounded,
  "ffmq-15": SelfImprovementRounded,
  "lee-love-styles": StarsRounded,
  "hexaco-pi-r-100": GrainRounded,
};

const TOPIC_FALLBACK: Record<string, IconType> = {
  "سلامت روان": HealthAndSafetyRounded,
  "فردی": PersonRounded,
  "زوج و خانواده": GroupsRounded,
  "شغلی": WorkRounded,
  "هوش": PsychologyRounded,
  "خلاقیت": LightbulbRounded,
  "تحصیلی": SchoolRounded,
  "سبک زندگی": SpaRounded,
};

export function psychTestIcon(slug: string | undefined, topicName?: string | null): IconType {
  if (slug && BY_SLUG[slug]) return BY_SLUG[slug];
  if (topicName && TOPIC_FALLBACK[topicName]) return TOPIC_FALLBACK[topicName];
  return PsychologyRounded;
}

export default psychTestIcon;
