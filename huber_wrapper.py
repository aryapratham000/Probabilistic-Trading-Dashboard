import statsmodels.api as sm

class HuberWrapper:
    def __init__(self):
        self.model = None
        self.feature_names = None

    def fit(self, X, y):
        Xc = sm.add_constant(X)
        self.model = sm.RLM(y, Xc, M=sm.robust.norms.HuberT()).fit()
        self.feature_names = X.columns.tolist()

    def predict(self, X_new):
        X_new = X_new[self.feature_names].copy()
        Xc = sm.add_constant(X_new, has_constant='add')
        return self.model.predict(Xc)

    def summary(self):
        return self.model.summary()
