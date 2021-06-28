#!/usr/bin/env python3
# App for data handling
# Copyright (C) 2020  Manish Anand
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from copy import deepcopy
from distutils.dir_util import copy_tree
import subprocess, json, threading, time, datetime, zipfile, os, shutil
import concurrent.futures
from pyorthanc import Orthanc

orthanc = Orthanc('http://localhost:8042')

name ="GEnii"
# helper class for common gui widgets
class Elements:
    def __init__(self, master):
        self.master = master

    # method for all button processes
    def button(self, char, funct, lambdaVal, x_, y_, algn, rows):
        if lambdaVal == '':
            self.b = tk.Button(self.master, text=char, command=funct)
        else:
            self.b = tk.Button(self.master, text=char, command=lambda: funct(lambdaVal))
        self.b.grid(row=y_, column=x_, sticky=algn, rowspan=rows, ipadx=5, ipady=5)

    # method for calling a text entry dialog
    def textField(self, lbl, w_, x_, y_):
        textField = tk.Entry(self.master, width=w_)
        textField.grid(row=y_, column=x_ + 1, sticky=tk.W, ipadx=5, ipady=5)
        textField_lbl = tk.Label(self.master, text=lbl)
        textField_lbl.grid(row=y_, column=x_, sticky=tk.E, ipadx=5, ipady=5)
        return textField

    def check(self, char, var, x_, y_):
        check = tk.Checkbutton(self.master, text=char, variable=var)
        check.grid(column=x_, row=y_)

    def label1(self, char, x_, y_, algn, rows, cols):
        self.b = tk.Label(self.master, text=char)
        self.b.grid(row=y_, column=x_, sticky=algn, rowspan=rows, columnspan=cols)

    def label2(self, charVariable, x_, y_, algn):
        self.b = tk.Label(self.master, textvariable=charVariable)
        self.b.grid(row=y_, column=x_, sticky=algn)

## ****************************************************************************************************************

class config:
    def __init__(self, project):
        self.project = project
        self.readSettings()
        self.allocate()

    def readSettings(self):
        with open(self.project) as settingsFile:
            self.settings_dict = json.load(settingsFile)

    def allocate(self):
        self.structure = self.settings_dict["structure"]
        self.unzippedDicoms = self.settings_dict["unzippedDicoms"]


    # def reverse_allocate(self):
    #     self.settings_dict["icaPath"] = self.icaPath
    #     self.settings_dict['prefeat_identifier'] = self.prefeat_identifier
    #     self.settings_dict['output_identifier'] = self.output_identifier
    #     self.settings_dict['user']=self.user_options
    #
    # def writeSettings(self):
    #     self.reverse_allocate()
    #     with open(Path(__file__).parent.absolute()/'settings.json', 'w') as json_file:
    #         json.dump(self.settings_dict, json_file)
    #
    # def loadDefaults(self):
    #     self.settings_dict["user"] = self.settings_dict["defaults"].copy()
#-----------------------------------------------------------------------------------------------------------------------

class MainArea(tk.Frame):
    def __init__(self, master, **kwargs):
        tk.Frame.__init__(self, master, **kwargs)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.master = master


        # Frame for all controls
        self.f1 = tk.LabelFrame(self, text='Controls', borderwidth=1, padx=10, pady=10, relief='raised')
        self.f1.grid(row=0, column=0, sticky='NSEW')

        # Frame for Tree View
        self.f2 = tk.Frame(self, borderwidth=0, relief='raised', pady=10)
        self.f2.grid(row=1, column=0, sticky='NSEW')
        self.f2.columnconfigure(0, weight=1)
        self.f2.rowconfigure(0, weight=1)
        self.dicomdl = tk.IntVar()

        # Display results and status
        headers = ["ID","Name","Date","DLS","Missing","Status"]
        headings = ["#", "Subject ID","Date", "Download Status","Missing", "Conversion Status"]
        self.result_tree = result_window(self.f2, headers, headings)
        # Controls
        el = Elements(self.f1)
        el.button("Database", self.dicom_database, '', 0, 0, tk.W + tk.E, 1)  # Selection of root directory
        el.button("Process", self.processThreader, '', 0, 1, tk.W + tk.E, 1)  # Process all data
        # self.dataset = el.textField("Task/Dataset", 20, 1, 0)  # Task or Dataset to be searched for
        # self.filters = el.textField("Filters", 20, 1, 1)  # keywords to filter individual datasets
        # el.button("Search", self.search, '', 3, 0, tk.N + tk.S, 1)  # button press to start search
        el.button("Clear", self.result_tree.clear, '', 3, 1, tk.N, 1)  # button press to clear selection
        # el.check('Overwrite', self.overwrite, 4, 1)  # checkbox for overwite option
        el.check('Download DICOMS only', self.dicomdl, 4, 1)  # checkbox for overwite option

        # options = [""]
        self.profiles = (Path(__file__).parent.absolute() / 'profiles').glob('*.json')
        options = [Path(i).stem for i in self.profiles]
        options.append("")
        self.project_selection = tk.StringVar()
        # initial menu text
        self.project_selection.set(options[-1])
        # Create Dropdown menu
        drop = tk.OptionMenu(self.f1, self.project_selection, *options)
        drop.grid(row=0, column=3)
        self.file_path = ''
        self.db = []

    def project(self):
        # find database location
        settings_file = (Path(__file__).parent.absolute()/'settings.json')
        with open(settings_file) as settingsFile:
            self.settings = json.load(settingsFile)
        #  Generate project specific paths
        project = self.project_selection.get()
        profile = (Path(__file__).parent.absolute() / 'profiles' / f'{project}.json')
        self.config = config(profile)
        self.database = Path(self.settings["database"] + project)
        if not Path(self.database).is_dir():
            appFuncs.initialize_storage(self.database, self.config.structure)

    def dicom_database(self):
        t1 = time.perf_counter()
        self.db = []
        patients_identifiers = orthanc.get_patients()
        for patient_identifier in patients_identifiers:
            patient = orthanc.get_patient_information(patient_identifier)
            patient_name = patient['MainDicomTags']['PatientID']
            study_identifiers = patient['Studies']
            study = orthanc.get_study_information(study_identifiers[0])
            num_series = study['Series'].__len__()
            date = study['MainDicomTags']['StudyDate']
            date_obj = datetime.datetime.strptime(date, '%Y%m%d')
            study_date = date_obj.date()
            stats = []
            series_description = []
            status = ''
            status_number = 0
            missing_series= []

### speed up
            for s in study['Series']:
                series = orthanc.get_series_information(s)
                series_description.append(series['MainDicomTags']['SeriesDescription'])
                stats.append(series['Status'])

            ls_missing = [i for i in range(len(stats)) if stats[i] == 'Missing']
            status_number = len(ls_missing)
            missing_series = [series_description[k] for k in ls_missing]
            if status_number > 0: status = 'Missing'

            pvp = -1
            row = [patient_name, patient['ID'], study_date, status, status_number, num_series, missing_series, pvp]

            self.db.append(row)
        self.result_tree.fileList = deepcopy(self.db)
        # Refresh results display
        self.result_tree.display()  # display the results
        t2 = time.perf_counter()

        print(f'Database Generated in {(t2 - t1)} Seconds')
        # self.file_list_gen()


    def file_list_gen(self):
        tmp_db = deepcopy(self.db)
        for row in tmp_db:
            patient_name = row[0]
            self.zip_name = appFuncs.generateZipPath(self.database, patient_name)
            self.nifti_path = appFuncs.generateNIFTIPath(self.database, patient_name)
            pvp = appFuncs.processed_status(self.zip_name, self.nifti_path, self.dicomdl.get())
            row[-1] = pvp
            row.extend([self.zip_name, self.nifti_path])


        self.result_tree.fileList = deepcopy(tmp_db)
        # Refresh results display
        self.result_tree.display()  # display the results

    def update_selection(self, *args):
        self.project()
        self.file_list_gen()

    def processThreader(self):
        self.update_idletasks()
        x = threading.Thread(target=self.process)
        x.daemon = True
        x.start()
    # Routed here from processThreader when Process button is pressed
    def process(self):
        # self.stat.set('Processing...')
        queue = self.result_tree.queue()
        t1 = time.perf_counter()
        process_queue = executor(queue, self.database, self.result_tree, self.config, self.dicomdl.get())
        if self.dicomdl.get() == 1:
            process_queue.threader1()  # put the queue on multi-threaded processing
        else:
            process_queue.threader()        # put the queue on multi-threaded processing
        # process_queue.threader1()        # put the queue on multi-threaded processing
        t2 = time.perf_counter()

        print(f'Processing Completed in {round((t2-t1)/60)} minutes')
        # self.stat.set(f'Processing Completed in {round((t2-t1)/60)} minutes')

class executor:
    def __init__(self, db, database_location, result_tree, config, dicomdl):
        self.fl = list
        self.database_location = database_location
        self.db = db
        self.result_tree = result_tree
        self.config = config
        self.dicomdl = dicomdl

    def execute_code1(self, queue):
        for que in queue:
            iid, subject_name, archive, pvp, fName_zip, nifti_path = [que[i] for i in list(range(0,len(que)))]
            # save zipped Dicoms files
            self.result_tree.processing_status(iid, 'Downloading Dicoms')
            bytes_content = orthanc.archive_patient(archive)
            with open(fName_zip, 'wb') as file_handler:
                file_handler.write(bytes_content)
            self.result_tree.processing_status(iid, 'Completed')

    def execute_code(self, que):
        iid, subject_name, archive, pvp, fName_zip, nifti_path = [que[i] for i in list(range(0,len(que)))]
        unzipped_location = Path(self.database_location/self.config.structure[2])
        # delete zip file if it already exists
        if pvp > 0 and Path(fName_zip).is_file():
            os.remove(fName_zip)
        # save zipped Dicoms files
        self.result_tree.processing_status(iid, 'Downloading Dicoms')
        bytes_content = orthanc.archive_patient(archive)
        with open(fName_zip, 'wb') as file_handler:
            file_handler.write(bytes_content)

        #  Extract zip
        self.result_tree.processing_status(iid, 'Extracting DICOMS')
        # print(fName_zip)
        dicomzip = zipfile.ZipFile(str(fName_zip))
        self.result_tree.processing_status(iid, 'Zip read')
        dicomzip.extractall(unzipped_location)
        self.result_tree.processing_status(iid, 'zip extracted')
        #

        # move Folders to main directory
        self.result_tree.processing_status(iid, 'Cleaning directory')
        fol = Path(unzipped_location).glob(subject_name + '*')
        folder_names = [Path(i) for i in fol]
        folder_name = folder_names[0]
        print(self.config.unzippedDicoms)
        if self.config.unzippedDicoms:
            s = Path(folder_name).glob('*Study')
            sl = [i for i in s]
            source_folder_all = sl[0]
            try:
                mpr = Path(source_folder_all).glob('*MPRAGE*/')
                mp = [m for m in mpr]
                source_folder = mp[0]
                print(source_folder)
                shutil.move(str(source_folder), str(folder_name))
            except:
                print('Folder not present.. moving on')

        #
        # Extract NIFTIS
        self.result_tree.processing_status(iid, 'Extracting NIFTIs')
        if not Path(nifti_path).is_dir():
            os.mkdir(nifti_path)

        args = ['dcm2niix', '-z','y', '-f', '%p', '-o', nifti_path, folder_name]
        print(args)
        subprocess.run(args)

        #  Delete all folders except the structural
        self.result_tree.processing_status(iid, 'Cleaning extras')
        if self.config.unzippedDicoms:
            shutil.rmtree(source_folder_all)

        self.result_tree.processing_status(iid, 'Completed')
        # self.result_tree[id][3] = 1

    def threader(self):
        que = self.queue_prep()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            ex.map(self.execute_code, que)

    def threader1(self):
        que = self.queue_prep()
        self.execute_code1(que)

    def queue_prep(self):
        que = []
        iid = [i for i in self.result_tree.tree.selection()]
        if iid == []:
            iid = range(0, len(self.db))
        for i in range(0, len(self.db)):
            var_list = (0, 1, 7, 8, 9)
            row = [iid[i]]+[self.db[i][j] for j in var_list] #+[structure, unzippedDicoms]
            que.append(row)
        return que
## 8****************************************************************************************************************8
class result_window:

    def __init__(self, parent,headers,headings):
        # Draw a treeview of a fixed type
        # self.viewer=viewer
        # self.stat=stat
        self.parent = parent
        self.database = []
        self.fileList = []
        self.tree = ttk.Treeview(self.parent, show='headings', columns=headers)
        self.tree.grid(sticky='NSEW')
        self.tree.column("#0", width =120, minwidth= 25)
        self.tree.heading("#0", text ="", anchor = 'w')
        widths = [30,200,100,150,100,150]
        for i in range(0,len(headers)):
            self.tree.heading(headers[i], text=headings[i])
            self.tree.column(headers[i], width=widths[i], stretch=tk.NO, anchor='center')
        self.tree.column(headers[1], width=widths[1], stretch=tk.NO, anchor='w')
        self.tree.column(headers[4], width=widths[4], stretch=tk.NO, anchor='e')
        self.tree.bind('<Button-1>',self.left_click)
        self.tree.bind('d', self.delete_entry)
        # self.tree.bind(('<Button-3>' ), self.double_left_click)
        # self.tree.bind(('<Button-2>'), self.double_left_click)
        # self.tree.bind(('w'), self.double_left_click)
        self.last_focus = None
        self.clickID = 1000000


    def display(self):
        self.delete()
        index = iid = 0

        for row in self.fileList:
            # patient_name, patient['ID'], study_date, status, status_number, num_series, missing_series, self.zip_name, self.nifti_path, pvp
            var_list =[0 ,2, 3, 4, 5, 6, 7]
            id, date, status, count, num_series, missing_series, pvp = [row[j] for j in var_list]
            transfer_count = f'{count}    of    {num_series:02}'
            sel = self.tree.insert("", index, iid, values=(iid + 1, id, date, status, transfer_count))
            if len(missing_series) != 0:
                m_id = 1
                for mis_ser in missing_series:
                    # m_id = iid*10+m_id
                    self.tree.insert(iid, "end", values=('', mis_ser, '', '', ''))
                    # m_id += 1
            status_msgs = ["Not Processed", "DICOMs Downloaded", "Processed","Select project"]
            self.processing_status(iid, status_msgs[pvp])
            index = iid = index + 1

    # generate queue for processing
    def queue(self):
        fl = self.fileList
        # id = list(range(0, len(fl)))
        index = self.tree.selection()
        print(index)
        # if any items are selected, modify the file list to be processed
        if len(index) != 0:
            N = [int(i) for i in index]
            fl = [fl[j] for j in N]
            # id = N
        return fl

    # clears selection of all items in treeview
    def clear(self):
        for item in self.tree.selection(): self.tree.selection_remove(item)

    # clears selection of line
    def clear_row(self, iid):
        self.tree.selection_remove(iid)

    def delete(self):
        self.tree.delete(*self.tree.get_children())

    # display status of a treeview item
    def processing_status(self, iid, stsMsg):
        self.tree.set(iid, 'Status', stsMsg)
        self.parent.update_idletasks()

    def left_click(self, event):
        try:
            iid = int(self.tree.identify_row(event.y))
        except:
            iid =''

        if not iid == '':
            self.clickID = iid

    # def double_left_click(self, event):
    #     iid = self.clickID
    #     if iid != '':
    #         self.clickID = ''
    #         iid = int(iid)
    #         outpath = self.fileList[iid][1]
    #         path = appFuncs.generateProcessedOutpath(outpath)
    #         pvp = self.fileList[iid][3]
    #         pop=self.fileList[iid][4]
    #         if pvp == 1:
    #             motion_IC_file = outpath / 'classified_motion_ICs.txt'
    #             h = open(motion_IC_file,'r')
    #             content =h.readlines()
    #             for line in content:
    #                 motion_IC = line.split(',')
    #                 motion_IC = list(map(int,motion_IC))
    #             im_list= []
    #             for IC in motion_IC:
    #                 im_list.append(outpath/'melodic.ica'/'report'/f'IC_{IC}_thresh.png')
    #                 mode = 2
    #
    #         if pop == 1 and pvp == 1:
    #             im_list_post = [path / 'rendered_thresh_zstat1.png', path / 'tsplot' / 'tsplot_zstat1.png']
    #             im_list += im_list_post
    #             mode = 3
    #         if pvp == 1:
    #             self.viewer.display(im_list, mode)


    def delete_entry(self, event):
        iid = self.clickID
        if not iid=='':
            iid=int(iid)
            del self.fileList[iid]
            self.delete()
            self.display()
            self.clickID = ''

## 8****************************************************************************************************************8
#   helper class for common use functions
class appFuncs:
    # generates output folder path
    @staticmethod
    def generateZipPath(database, patient_name):
        zipFileName = str(Path(database / 'DICOMS' / (patient_name + '.zip')))
        return zipFileName


    @staticmethod
    def generateUnZipPath(unzipped_location, patient_name):
        unzipFolderName = ''
        fol = Path(unzipped_location).glob(patient_name + '*')
        f = [i for i in fol]
        if len(f) != 0: unzipFolderName = f[0]
        return unzipFolderName



    @staticmethod
    def generateNIFTIPath(database, patient_name):
        niftipath = Path(database / 'Data' / patient_name/'NIFTI')
        return niftipath

    # Identify previously processed datasets
    @staticmethod
    def processed_status(zip_name, nifti_path, dicomdl):
        pvp = 0
        if Path(zip_name).is_file():
            pvp = 1

        if Path(nifti_path).is_dir() and not dicomdl:
            pvp = 2

        return pvp

    @staticmethod
    def initialize_storage(location, sub_folders):
        os.mkdir(location)
        for sub_folder in sub_folders:
            os.mkdir(Path(location)/sub_folder)


#-----------------------------------------------------------------------------------------------------------------------

class MainApp(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        parent.title(name)
        parent.minsize(800,500)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # draw a viewer window
        # viewer_root=tk.Toplevel()
        # self.config=config()
        # Components
        # self.viewer = Viewer(viewer_root)
        # self.menubar = Menubar(parent,self.config)
        # self.statusbar = StatusBar(parent)
        self.mainarea = MainArea(parent, borderwidth=1, relief=tk.RAISED)
        self.mainarea.project_selection.trace("w", self.mainarea.update_selection)
        # configurations
        self.mainarea.grid(column=0, row=0, sticky='WENS')
        # self.statusbar.grid(column=0, row=1, sticky='WE')
        # self.statusbar.set('Ready')
#-----------------------------------------------------------------------------------------------------------------------
root = tk.Tk()
PR = MainApp(root)
root.mainloop()


# sudo mount -t cifs -o username=manand9@EMORYUNIVAD,dir_mode=0777,file_mode=0777 //10.224.18.6/orthofb/SPARC/ /mnt/share