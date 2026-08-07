from fastapi import APIRouter

from app.config import REGIONS, VARIABLES, INITIALIZATIONS, PERIOD_LABELS
from app.models import MetaResponse, RegionMeta, InitMeta

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    return MetaResponse(
        regions=[RegionMeta(key=k, label=v["label"], box=v["box"]) for k, v in REGIONS.items()],
        variables=VARIABLES,
        initializations=[
            InitMeta(key=k, label=v["label"], short_label=v["short_label"], periods=v["periods"], note=v["note"])
            for k, v in INITIALIZATIONS.items()
        ],
        period_labels=PERIOD_LABELS,
    )
