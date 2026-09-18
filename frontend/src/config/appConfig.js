export const APP_CONFIG = {
  name: "NexaBiz ERP",
  shortName: "NexaBiz",
  tagline: "A practical business operating system for growing small businesses.",
  defaultLocale: "en-US",
  defaultCurrency: "USD",
};

export function getBusinessPreferences() {
  return {
    locale: localStorage.getItem("nexabiz_locale") || APP_CONFIG.defaultLocale,
    currency: localStorage.getItem("nexabiz_currency") || APP_CONFIG.defaultCurrency,
    language: localStorage.getItem("nexabiz_language") || "en",
    timezone: localStorage.getItem("nexabiz_timezone") || "UTC",
  };
}

export function saveBusinessPreferences({ locale, currency, language, timezone }) {
  if (locale) localStorage.setItem("nexabiz_locale", locale);
  if (currency) localStorage.setItem("nexabiz_currency", currency);
  if (language) localStorage.setItem("nexabiz_language", language);
  if (timezone) localStorage.setItem("nexabiz_timezone", timezone);
}
