from django import template

register = template.Library()

FIFA_TO_ISO2 = {
    # UK nations
    "ENG": "GB", "SCO": "GB", "WAL": "GB", "NIR": "GB",
    # Asia/Middle East
    "KOR": "KR", "IRN": "IR", "IRQ": "IQ", "KSA": "SA", "UAE": "AE", "JOR": "JO",
    # Europe mismatches
    "GER": "DE", "NED": "NL", "POR": "PT", "DEN": "DK", "CRO": "HR",
    "TUR": "TR", "UKR": "UA", "SRB": "RS", "AUT": "AT",
    # Americas mismatches
    "MEX": "MX", "URU": "UY", "PAR": "PY", "HON": "HN", "GUA": "GT",
    "CRC": "CR", "TRI": "TT", "JAM": "JM", "HAI": "HT", "CUB": "CU", "PAN": "PA",
    # Africa
    "CIV": "CI", "CMR": "CM", "NGA": "NG", "SEN": "SN", "GHA": "GH",
    "MAR": "MA", "TUN": "TN", "EGY": "EG", "ALG": "DZ", "RSA": "ZA",
}


@register.filter
def flag_emoji(fifa_code):
    if not fifa_code:
        return ""
    iso2 = FIFA_TO_ISO2.get(fifa_code, fifa_code[:2]).upper()
    return chr(0x1F1E6 + ord(iso2[0]) - ord("A")) + chr(0x1F1E6 + ord(iso2[1]) - ord("A"))
