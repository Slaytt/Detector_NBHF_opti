"""writing of Res_*.txt and BilanTot.txt."""

def writeChannel(path, dates):
    with open(path, "w", encoding="utf-8") as f:
        for d in dates:
            f.write("%.16g\n" % d)

def writeMerged(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for date, canal in rows:
            f.write("%.16g\t%.16g\n" % (date, canal))

def bilanHeader(seuil, coefUmbral, fcutLow, fcutHigh, f1clic, f2clic, f1, f2):
    return (
        "Seuil: %f, coef_umbral %d, frequence coupure basse %d, frequence coupure haute %d,\n"
        % (seuil, coefUmbral, fcutLow, fcutHigh)
        + "BP du clic %d - %d, BP de référence %d - %d  \n" % (f1clic, f2clic, f1, f2)
        + "  \n"
        + " Detections : \n"
        + "Fichier \t canal 1 \t canal 2 \t total \n"
    )

def bilanLine(fileName, n1, n2, n):
    return "%s \t %d \t %d \t %d \n" % (fileName, n1, n2, n)

def bilanFooter(duration):
    return "\nDuree totale %f s \n" % duration
