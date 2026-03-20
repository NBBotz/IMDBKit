import logging

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ("en", "fr-ca", "fr", "hi", "de", "it", "es", "pt", "es-es")
LOCALE_TO_COUNTRY_CODE = {
    "en": "EN",
    "fr-ca": "FR",
    "fr": "FR",
    "hi": "IN",
    "de": "DE",
    "it": "IT",
    "es": "ES",
    "pt": "PT",
    "es-es": "ES",
}
DEFAULT_LOCALE = "en"
_configured_locale = None


def set_locale(locale: str):
    global _configured_locale
    if not isinstance(locale, str):
        logger.warning(
            "Invalid locale type: %r. Locale must be a string. Falling back to default '%s'.",
            locale,
            DEFAULT_LOCALE,
        )
        _configured_locale = DEFAULT_LOCALE
        return
    l = locale.strip()
    if l not in SUPPORTED_LOCALES:
        logger.warning(
            "Locale '%s' is not supported. Falling back to default '%s'.", l, DEFAULT_LOCALE
        )
        _configured_locale = DEFAULT_LOCALE
        return
    _configured_locale = l


def _normalize_locale(lcl: str):
    if lcl not in SUPPORTED_LOCALES:
        logger.warning("Locale '%s' is not supported. Using '%s'", lcl, DEFAULT_LOCALE)
        return DEFAULT_LOCALE
    return lcl


def get_locale():
    lcl = _configured_locale or DEFAULT_LOCALE
    lcl = _normalize_locale(lcl)
    return "" if lcl == DEFAULT_LOCALE else lcl


def _retrieve_url_lang(locale=None):
    lcl = locale or _configured_locale or DEFAULT_LOCALE
    lcl = _normalize_locale(lcl)
    return "" if lcl == DEFAULT_LOCALE else lcl


def _get_country_code_from_lang_locale(locale=None):
    lcl = locale or _configured_locale or DEFAULT_LOCALE
    lcl = _normalize_locale(lcl)
    return LOCALE_TO_COUNTRY_CODE.get(lcl, LOCALE_TO_COUNTRY_CODE[DEFAULT_LOCALE])
