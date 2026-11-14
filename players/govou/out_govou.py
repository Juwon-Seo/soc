for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
    if v[0] != "same": print(d, o, v)
print("gr_mean", gr_mean("2010-11"), INTERP)
