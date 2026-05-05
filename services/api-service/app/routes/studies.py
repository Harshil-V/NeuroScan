from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.orthanc import OrthancClient
from app.routes.dicom import get_orthanc_client
from app.schemas.study import (
    InstanceListOut,
    InstanceOut,
    SeriesOut,
    StudyDetailOut,
    StudyListOut,
    StudyOut,
)

router = APIRouter(prefix="/api", tags=["studies"])


def _study_from_orthanc(detail: dict) -> StudyOut:
    tags = detail.get("MainDicomTags", {})
    patient_tags = detail.get("PatientMainDicomTags", {})
    series_ids = detail.get("Series", [])
    return StudyOut(
        orthanc_study_id=detail["ID"],
        study_instance_uid=tags.get("StudyInstanceUID", ""),
        patient_id=patient_tags.get("PatientID"),
        modality=tags.get("ModalitiesInStudy") or tags.get("Modality"),
        study_date=tags.get("StudyDate"),
        study_description=tags.get("StudyDescription"),
        series_count=len(series_ids),
        instance_count=detail.get("Statistics", {}).get("CountInstances")
        or sum(1 for _ in series_ids),  # fallback approximation
    )


@router.get("/studies", response_model=StudyListOut)
async def list_studies(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> StudyListOut:
    studies = await orthanc.list_studies()
    total = len(studies)
    page = studies[offset : offset + limit]
    items = [_study_from_orthanc(s) for s in page]
    return StudyListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/studies/{study_instance_uid}", response_model=StudyDetailOut)
async def get_study(
    study_instance_uid: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> StudyDetailOut:
    orthanc_study_id = await orthanc.find_study_by_uid(study_instance_uid)
    if not orthanc_study_id:
        raise HTTPException(status_code=404, detail="study_not_found")
    detail = await orthanc.get_study(orthanc_study_id)
    series_out: list[SeriesOut] = []
    for series_id in detail.get("Series", []):
        s = await orthanc.get_series(series_id)
        s_tags = s.get("MainDicomTags", {})
        series_out.append(
            SeriesOut(
                orthanc_series_id=s["ID"],
                series_instance_uid=s_tags.get("SeriesInstanceUID", ""),
                series_description=s_tags.get("SeriesDescription"),
                modality=s_tags.get("Modality"),
                series_number=int(s_tags["SeriesNumber"]) if s_tags.get("SeriesNumber") else None,
                instance_count=len(s.get("Instances", [])),
            )
        )
    base = _study_from_orthanc(detail)
    return StudyDetailOut(**base.model_dump(), series=series_out)


@router.get(
    "/series/{series_instance_uid}/instances",
    response_model=InstanceListOut,
)
async def list_series_instances(
    series_instance_uid: str,
    orthanc: OrthancClient = Depends(get_orthanc_client),
) -> InstanceListOut:
    orthanc_series_id = await orthanc.find_series_by_uid(series_instance_uid)
    if not orthanc_series_id:
        raise HTTPException(status_code=404, detail="series_not_found")
    detail = await orthanc.get_series(orthanc_series_id)
    items: list[InstanceOut] = []
    for inst_id in detail.get("Instances", []):
        inst = await orthanc.get_instance(inst_id)
        tags = inst.get("MainDicomTags", {})
        items.append(
            InstanceOut(
                orthanc_instance_id=inst["ID"],
                sop_instance_uid=tags.get("SOPInstanceUID", ""),
                instance_number=int(tags["InstanceNumber"]) if tags.get("InstanceNumber") else None,
                rows=int(tags["Rows"]) if tags.get("Rows") else None,
                columns=int(tags["Columns"]) if tags.get("Columns") else None,
            )
        )
    return InstanceListOut(items=items)
