"""decision rules: a rule takes the candidate table and returns one boolean per row."""

def thresholdRule(table, seuil):
    return table["levelClick"] > seuil * table["levelRef"]
