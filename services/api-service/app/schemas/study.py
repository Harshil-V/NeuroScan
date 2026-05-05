from pydantic import BaseModel


class SeriesOut(BaseModel):
    orthanc_series_id: str
    series_instance_uid: str
    series_description: str | None
    modality: str | None
    series_number: int | None
    instance_count: int


class StudyOut(BaseModel):
    orthanc_study_id: str
    study_instance_uid: str
    patient_id: str | None
    modality: str | None
    study_date: str | None
    study_description: str | None
    series_count: int
    instance_count: int


class StudyDetailOut(StudyOut):
    series: list[SeriesOut]


class StudyListOut(BaseModel):
    items: list[StudyOut]
    total: int
    limit: int
    offset: int


class InstanceOut(BaseModel):
    orthanc_instance_id: str
    sop_instance_uid: str
    instance_number: int | None
    rows: int | None
    columns: int | None


class InstanceListOut(BaseModel):
    items: list[InstanceOut]
