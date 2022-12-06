#! /usr/bin/env python3

"""
pyWhat: Identify Anything.
"""

import platform
import sys
import what
import threading

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QVBoxLayout, QWidget, QMenu, QCheckBox, QScrollArea

# class for scrollable label
class ScrollLabel(QScrollArea):
 
    # constructor
    def __init__(self, *args, **kwargs):
        QScrollArea.__init__(self, *args, **kwargs)
 
        # making widget resizable
        self.setWidgetResizable(True)
 
        # making qwidget object
        content = QWidget(self)
        self.setWidget(content)
 
        # vertical box layout
        lay = QVBoxLayout(content)
 
        # creating label
        self.label = QLabel(content)
 
        # setting alignment to the text
        # self.label.setAlignment(Qt.Al | Qt.AlignTop)
 
        # making label multi-line
        self.label.setWordWrap(True)
 
        # adding label to the layout
        lay.addWidget(self.label)
 
    # the setText method
    def setText(self, ):
        # setting text to the label
        history_file = open('history.dat', 'r')
        history = history_file.read()
        history_file.close()
        self.label.setText(history)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyWhat-GUI")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter your phrase here.")
        self.input.returnPressed.connect(self.searchThis)   
        self.button = QPushButton("PyWhat Me!")
        self.button.setCheckable(True)
        self.button.clicked.connect(self.searchThis)
        self.history = ScrollLabel(self)
        self.history.setText()
        layout = QVBoxLayout()
        # layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.button)
        layout.addWidget(self.history)
        self.container = QWidget()
        self.container.setLayout(layout)
        self.setFixedSize(QSize(400, 300))
        # Set the central widget of the Window.
        self.setCentralWidget(self.container)

    def pywhatThread(self, search):
        sys.stdout = open('history.dat', 'a')
        # print("Searching: ", search)
        what.run({search})
        # print("result", result)
        sys.stdout.close()
    def searchThis(self):
        # print("Clicked!")
        search = self.input.text()
        pythread = threading.Thread(target=self.pywhatThread, args=(search,))
        pythread.start()
        import time
        time.sleep(0.5)
        pythread.join()
        # self.pywhatThread(search)
        self.history.setText()


    # def contextMenuEvent(self, e):
    #     context = QMenu(self)
    #     context.addAction(QAction("test 1", self))
    #     context.addAction(QAction("test 2", self))
    #     context.addAction(QAction("test 3", self))
    #     context.exec(e.globalPos())
    


if __name__ == "__main__":
    if sys.version_info < (3, 6):
        print(
            f"What requires Python 3.6+, you are using {platform.python_version()}. Please install a higher Python version."
        )
        sys.exit(1)

    # from pywhat import what
    app = QApplication(sys.argv)
    global window 
    window = MainWindow()
    window.show()
    app.exec()

    

    # if len(sys.argv) == 1:
    #     what.main(["--help"])

    # what.main()
