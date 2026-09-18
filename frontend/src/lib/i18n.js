const messages = {
  en: { settings: "Settings", businessProfile: "Business Profile", save: "Save", language: "Language", timezone: "Timezone", tax: "Tax" },
  id: { settings: "Pengaturan", businessProfile: "Profil Bisnis", save: "Simpan", language: "Bahasa", timezone: "Zona waktu", tax: "Pajak" },
};

export function getLanguage() {
  return localStorage.getItem("nexabiz_language") || "en";
}

export function t(key) {
  return messages[getLanguage()]?.[key] || messages.en[key] || key;
}

export const SUPPORTED_LANGUAGES = [
  { value: "en", label: "English" },
  { value: "id", label: "Bahasa Indonesia" },
];
