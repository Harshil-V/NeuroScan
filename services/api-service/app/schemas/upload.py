from pydantic import BaseModel


class UploadResult(BaseModel):
    status: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    orthanc_instance_id: str
    checksum_sha256: str


class ApiError(BaseModel):
    detail: str
    code: str | None = None
