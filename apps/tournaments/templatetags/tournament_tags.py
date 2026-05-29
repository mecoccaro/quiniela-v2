from django import template

register = template.Library()

FIFA_TO_ISO2 = {
    "ENG": "GB", "SCO": "GB", "WAL": "GB", "NIR": "GB",
    "KOR": "KR", "IRN": "IR", "KSA": "SA", "UAE": "AE",
    "CRC": "CR", "TRI": "TT", "CIV": "CI", "CMR": "CM",
    "NGA": "NG", "SEN": "SN", "GHA": "GH", "MAR": "MA",
    "TUN": "TN", "EGY": "EG", "ALG": "DZ", "RSA": "ZA",
    "PAN": "PA", "JAM": "JM", "HAI": "HT", "CUB": "CU",
}


@register.filter
def flag_emoji(fifa_code):
    if not fifa_code:
        return ""
    iso2 = FIFA_TO_ISO2.get(fifa_code, fifa_code[:2]).upper()
    return chr(0x1F1E6 + ord(iso2[0]) - ord("A")) + chr(0x1F1E6 + ord(iso2[1]) - ord("A"))
