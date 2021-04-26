from pyorthanc import Orthanc
orthanc = Orthanc('http://localhost:8042')

# To get patients identifier and main information
patients_identifiers = orthanc.get_patients()

for patient_identifier in patients_identifiers:
    patient = orthanc.get_patient_information(patient_identifier)
    patient_name = patient['MainDicomTags']['PatientID']
    study_identifiers = patient['Studies']


    fName = patient_name+'.zip'
    print(fName)
    bytes_content = orthanc.archive_patient(patient['ID'])
    with open(fName, 'wb') as file_handler:
        file_handler.write(bytes_content)
