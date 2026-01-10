import sys
from pathlib import Path

# On ajoute le chemin racine du projet pour trouver les modules services
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "services" / "prefect"))

from compare_utils import should_promote

def test_should_promote_when_better_than_prod_plus_delta():
    # 0.80 > 0.78 + 0.01 (0.79) -> True
    assert should_promote(new_auc=0.80, prod_auc=0.78, delta=0.01) is True

def test_should_not_promote_when_not_enough_gain():
    # 0.785 n'est pas > 0.78 + 0.01 (0.79) -> False
    assert should_promote(new_auc=0.785, prod_auc=0.78, delta=0.01) is False

