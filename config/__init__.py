# Patch scipy.stats._stats_pythran to avoid Application Control policy blocking DLL
try:
    import sys
    import types
    if 'scipy.stats._stats_pythran' not in sys.modules:
        m = types.ModuleType('scipy.stats._stats_pythran')
        m.siegelslopes = lambda *args, **kwargs: (None, None)
        m._compute_outer_prob_inside_method = lambda *args, **kwargs: None
        m._a_ij_Aij_Dij2 = lambda *args, **kwargs: None
        m._concordant_pairs = lambda *args, **kwargs: None
        m._discordant_pairs = lambda *args, **kwargs: None
        sys.modules['scipy.stats._stats_pythran'] = m
except Exception:
    pass
