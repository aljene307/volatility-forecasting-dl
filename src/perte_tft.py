"""Perte MSE pour le TFT de pytorch-forecasting, qui ne fournit que RMSE.

Même perte que les autres modèles (erreur quadratique sur log(RV) normalisée). Classe définie au niveau
du module pour que le modèle puisse être sauvegardé (pickle).
"""

from pytorch_forecasting.metrics.base_metrics import MultiHorizonMetric


class MSE(MultiHorizonMetric):
    def loss(self, y_pred, target):
        return (self.to_prediction(y_pred) - target) ** 2
