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
from distutils.dir_util import copy_tree
import subprocess, json, threading, time, datetime, zipfile, os, shutil
import concurrent.futures
from pyorthanc import Orthanc

orthanc = Orthanc('http://localhost:8042')

name ="genii"
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

        # Individual elements
        self.database = Path('/home/linuxbox1/Database/')
        # Display results and status
        headers = ["ID","Name","Date","DLS","Missing","Status"]
        headings = ["#", "Subject ID","Date", "Download Status","Missing" ,"Conversion Status"]
        self.result_tree = result_window(self.f2, self.database, headers,headings)
        # Controls
        el = Elements(self.f1)
        el.button("Database", self.selectPath, '', 0, 0, tk.W + tk.E, 1)  # Selection of root directory
        el.button("Process", self.processThreader, '', 0, 1, tk.W + tk.E, 1)  # Process all data
        # self.dataset = el.textField("Task/Dataset", 20, 1, 0)  # Task or Dataset to be searched for
        # self.filters = el.textField("Filters", 20, 1, 1)  # keywords to filter individual datasets
        # el.button("Search", self.search, '', 3, 0, tk.N + tk.S, 1)  # button press to start search
        el.button("Clear", self.result_tree.clear, '', 3, 1, tk.N, 1)  # button press to clear selection
        # el.check('Overwrite', self.overwrite, 4, 1)  # checkbox for overwite option

        self.file_path = ''
        self.db = []

    def selectPath(self):
        self.db = []
        patients_identifiers = orthanc.get_patients()

        for patient_identifier in patients_identifiers:
            patient = orthanc.get_patient_information(patient_identifier)
            patient_name = patient['MainDicomTags']['PatientID']
            study_identifiers = patient['Studies']
            study = orthanc.get_study_information(study_identifiers[0])
            date = study['MainDicomTags']['StudyDate']
            date_obj = datetime.datetime.strptime(date, '%Y%m%d')
            study_date = date_obj.date()
            stats = []
            series_description =[]
            missing_series=[]
            for s in study['Series']:
                series = orthanc.get_series_information(s)
                series_description.append(series['MainDicomTags']['SeriesDescription'])
                stats.append(series['Status'])

            status_number = 0
            for i in range(0,len(stats)):
                if stats[i] == 'Missing':
                    missing_series.append(series_description[i])

            if 'Missing' in stats:
                status = 'Missing'
                status_number = stats.count('Missing')
            else:
                status = ''


            self.zip_name = appFuncs.generateZipPath(self.database, patient_name)
            # self.unzipped_location = Path(self.database / 'Unzipped')
            # self.fol = appFuncs.generateUnZipPath(self.unzipped_location, patient_name)
            self.nifti_path = appFuncs.generateNIFTIPath(self.database, patient_name)
            pvp = appFuncs.processed_status(self.nifti_path)
            row = [patient_name, study_date, status,status_number,missing_series,self.zip_name, self.nifti_path, pvp, patient['ID']]
            self.db.append(row)

        self.result_tree.fileList = self.db
        # print(self.db[2])
        # Refresh results display
        self.result_tree.display()  # display the results

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
        process_queue = executor(queue, self.database, self.result_tree)
        process_queue.threader()        # put the queue on multi-threaded processing
        t2 = time.perf_counter()

        print(f'Processing Completed in {round((t2-t1)/60)} minutes')
        # self.stat.set(f'Processing Completed in {round((t2-t1)/60)} minutes')

class executor:
    def __init__(self,db,database_location,result_tree):
        self.fl = list
        self.database_location = database_location
        self.db = db
        self.result_tree = result_tree

    def execute_code1(self, que):
        pass

    def execute_code(self, que):
        # args = que[0]
        # [iid[i], patient_name, self.database_location, zipFile, niftiPath, archive]
        id = que[0]
        name = que[1]
        database_location = que[2]
        fName_zip = que[3]
        unzipped_location = Path(database_location/'Structural')

        nifti_path = que[4]
        archive = que[5]
        # save zipped Dicoms files
        self.result_tree.processing_status(id, 'Downloading Dicoms')
        bytes_content = orthanc.archive_patient(archive)
        with open(fName_zip, 'wb') as file_handler:
            file_handler.write(bytes_content)
        #
        #
        #  Extract zip
        self.result_tree.processing_status(id, 'Extracting DICOMS')
        dicomzip = zipfile.ZipFile(str(fName_zip))
        dicomzip.extractall(unzipped_location)
        #
        #
        # move Folders to main directory
        self.result_tree.processing_status(id, 'Cleaning directory')
        fol = Path(unzipped_location).glob(name + '*')
        folder_names = [Path(i) for i in fol]
        folder_name = folder_names[0]
        s = Path(folder_name).glob('*Study')
        sl = [i for i in s]
        source_folder_all = sl[0]
        mpr = Path(source_folder_all).glob('*MPRAGE*/')
        mp = [m for m in mpr]
        source_folder = mp[0]
        print(source_folder)
        shutil.move(str(source_folder), str(folder_name))
        # copy_tree(str(source_folder), str(folder_name))
        # shutil.rmtree(source_folder)
        #
        # Extract NIFTIS
        self.result_tree.processing_status(id, 'Extracting NIFTIs')
        if not Path(nifti_path).is_dir():
            os.mkdir(nifti_path)

        args = ['dcm2niix','-z','y','-o',nifti_path,folder_name]
        print(args)
        # subprocess.run(args)

        #  Delete all folders except the structural
        self.result_tree.processing_status(id, 'Cleaning extras')
        shutil.rmtree(source_folder_all)



        self.result_tree.processing_status(id, 'Completed')
        # self.result_tree[id][3] = 1

    def threader(self):
        que = self.queue_prep()
        with concurrent.futures.ThreadPoolExecutor() as ex:
            ex.map(self.execute_code, que)

    def queue_prep(self):
        que=[]
        iid = [i for i in self.result_tree.tree.selection()]
        if iid == []:
            iid = range(0,len(self.db))
        for i in range(0,len(self.db)):
            patient_name = self.db[i][0]
            zipFile = self.db[i][5]
            niftiPath = self.db[i][6]
            # fName_zip = str(Path(self.database_location /'Zipped'/ (self.db[i][0] + '.zip')))
            # fName = str(Path(self.database_location / self.db[i][0]))
            # row = [patient_name, study_date, status,status_number,missing_series,self.zip_name, self.nifti_path, pvp, patient['ID']]
            archive = self.db[i][-1]
            row = [iid[i], patient_name, self.database_location, zipFile, niftiPath,archive]
            que.append(row)
        return que
## 8****************************************************************************************************************8
class result_window:

    def __init__(self, parent,database,headers,headings):
        # Draw a treeview of a fixed type
        # self.viewer=viewer
        # self.stat=stat
        self.parent = parent
        self.database = database
        self.fileList = []
        self.tree = ttk.Treeview(self.parent, show='headings', columns=headers)
        self.tree.grid(sticky='NSEW')
        self.tree.column("#0", width =120, minwidth= 25)
        self.tree.heading("#0", text ="", anchor = 'w')
        widths = [30,200,100,150,100,100]
        for i in range(0,len(headers)):
            self.tree.heading(headers[i], text=headings[i])
            self.tree.column(headers[i], width=widths[i], stretch=tk.NO, anchor='center')
        self.tree.column(headers[1], width=widths[1], stretch=tk.NO, anchor='w')
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
            id = row[0]
            date = row[1]
            status = row[2]
            count = row[3]
            missing_series = row[4]
            pvp = row[-2]
            sel = self.tree.insert("", index, iid, values=(iid + 1, id, date,status, count))
            if len(missing_series)!=0:
                m_id = 1
                for mis_ser in missing_series:
                    # m_id = iid*10+m_id
                    self.tree.insert(iid, "end", values=('', mis_ser, '', '', ''))
                    # m_id += 1


            # self.motion_stats(iid, motion)

            if pvp == 0:
                self.processing_status(iid, 'Not Processed')
            # elif pop==0:
            #     self.processing_status(iid, 'Processed')
            else:
                self.processing_status(iid, 'Processed')
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
        iid = int(self.tree.identify_row(event.y))
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
        niftipath = Path(database / 'NIFTI' / patient_name)
        return niftipath

    # Identify previously processed datasets
    @staticmethod
    def processed_status(nifti_path):
        if Path(nifti_path).is_dir():
            pvp = 1
        else:
            pvp = 0
        return pvp


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

        # configurations
        self.mainarea.grid(column=0, row=0, sticky='WENS')
        # self.statusbar.grid(column=0, row=1, sticky='WE')
        # self.statusbar.set('Ready')
#-----------------------------------------------------------------------------------------------------------------------
root = tk.Tk()
PR = MainApp(root)
root.mainloop()
