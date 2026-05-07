from io import BytesIO

import numpy as np
import pydicom

from app.services.reconstruction.dicom_writer import image_to_mr_dicom


def test_image_to_mr_dicom_returns_parseable_bytes():
    image = np.random.default_rng(0).integers(0, 4095, (64, 64), dtype=np.uint16)
    result = image_to_mr_dicom(image, source_name="test.npy")
    assert len(result.dicom_bytes) > 0
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.Modality == "MR"
    assert int(ds.Rows) == 64
    assert int(ds.Columns) == 64


def test_image_to_mr_dicom_required_tags_present():
    image = np.zeros((32, 32), dtype=np.uint16)
    result = image_to_mr_dicom(image, source_name="x.npy")
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.BitsAllocated == 16
    assert ds.BitsStored == 16
    assert ds.PhotometricInterpretation == "MONOCHROME2"
    assert ds.SamplesPerPixel == 1
    assert ds.PixelRepresentation == 0
    # UIDs all match what we returned
    assert str(ds.StudyInstanceUID) == result.study_instance_uid
    assert str(ds.SeriesInstanceUID) == result.series_instance_uid
    assert str(ds.SOPInstanceUID) == result.sop_instance_uid


def test_image_to_mr_dicom_uids_are_fresh_each_call():
    image = np.zeros((16, 16), dtype=np.uint16)
    a = image_to_mr_dicom(image, source_name="a.npy")
    b = image_to_mr_dicom(image, source_name="b.npy")
    assert a.study_instance_uid != b.study_instance_uid
    assert a.series_instance_uid != b.series_instance_uid
    assert a.sop_instance_uid != b.sop_instance_uid


def test_image_to_mr_dicom_pixel_array_round_trips():
    image = np.arange(0, 1024, dtype=np.uint16).reshape(32, 32)
    result = image_to_mr_dicom(image, source_name="x.npy")
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    np.testing.assert_array_equal(ds.pixel_array, image)


def test_image_to_mr_dicom_uses_provenance_metadata():
    image = np.zeros((16, 16), dtype=np.uint16)
    result = image_to_mr_dicom(
        image,
        source_name="brain_kspace.npz",
        patient_id="MY-ID",
        study_description="Custom Study",
        series_description="Custom Series",
    )
    ds = pydicom.dcmread(BytesIO(result.dicom_bytes))
    assert ds.PatientID == "MY-ID"
    assert ds.StudyDescription == "Custom Study"
    assert ds.SeriesDescription == "Custom Series"
