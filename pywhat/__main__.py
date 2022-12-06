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
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QVBoxLayout, QWidget, QMenu, QCheckBox

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyWhat-GUI")

        # self.label = QLabel("Enter Phrase Here")
        # font = self.label.font()
        # font.setPointSize(16)
        # self.label.setFont(font)
        # self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter your phrase here.")
        self.input.returnPressed.connect(self.searchThis)
        
        button = QPushButton("PyWhat Me!")
        button.setCheckable(True)
        button.clicked.connect(self.searchThis)

        layout = QVBoxLayout()
        # layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(button)

        

        self.container = QWidget()
        self.container.setLayout(layout)

        self.setFixedSize(QSize(400, 300))

        # Set the central widget of the Window.
        self.setCentralWidget(self.container)

    def searchThis(self):
        # print("Clicked!")
        search = self.input.text()
        # print(self.input.text())
        # sys.stdout = open('out.dat', 'w')
        result = what.run({search})
        print("result", result)
        # sys.stdout.close()


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
