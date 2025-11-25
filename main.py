import sys
import os
import re
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QLineEdit,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
)
from PySide6.QtCore import Qt
from pdf_processor import PdfWorker

def natural_sort_key(s):
    """
    A key function for natural sorting.
    Splits the string into a list of strings and numbers.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'([0-9]+)', s)]

# --- Folder Selection Dialog ---
class FolderSelectionDialog(QDialog):
    """
    A dialog window that allows the user to select and reorder folders.
    """
    def __init__(self, folders, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select and Order Folders")
        self.setGeometry(200, 200, 500, 600)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        # Enable drag-and-drop to reorder items
        self.list_widget.setDragDropMode(QListWidget.InternalMove)

        # Populate the list with the found sub-folders
        for folder in folders:
            item = QListWidgetItem(folder)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked) # Default to checked
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        # Standard OK and Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_folders_in_order(self):
        """
        Retrieves the list of checked folders in their current order.
        """
        selected_folders = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_folders.append(item.text())
        return selected_folders

# --- Main Application Window ---
class MainWindow(QMainWindow):
    """
    The main application window for the QBank PDF Generator.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QBank PDF Generator")
        self.setGeometry(100, 100, 700, 250)

        # --- Member variables ---
        self.root_folder_path = ""
        self.selected_folders = []

        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Root Folder Selection UI ---
        root_folder_layout = QHBoxLayout()
        root_folder_layout.addWidget(QLabel("Root Folder:"))
        self.root_folder_label = QLineEdit("No folder selected...")
        self.root_folder_label.setReadOnly(True)
        root_folder_layout.addWidget(self.root_folder_label)
        choose_root_folder_button = QPushButton("Choose Folder...")
        choose_root_folder_button.clicked.connect(self.select_root_folder)
        root_folder_layout.addWidget(choose_root_folder_button)
        main_layout.addLayout(root_folder_layout)

        # --- Output File Selection UI ---
        output_file_layout = QHBoxLayout()
        output_file_layout.addWidget(QLabel("Output PDF:"))
        self.output_path_label = QLineEdit("No file specified...")
        self.output_path_label.setReadOnly(True)
        self.output_path_label.textChanged.connect(self.validate_inputs)
        output_file_layout.addWidget(self.output_path_label)
        choose_output_button = QPushButton("Set Output File...")
        choose_output_button.clicked.connect(self.select_output_file)
        output_file_layout.addWidget(choose_output_button)
        main_layout.addLayout(output_file_layout)

        # --- Selected Folders Info Label ---
        self.selected_folders_label = QLabel("Selected folders: 0")
        main_layout.addWidget(self.selected_folders_label)

        # --- Bottom Bar with Start Button and Status Label ---
        bottom_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Generation")
        self.start_button.clicked.connect(self.start_processing)
        bottom_layout.addWidget(self.start_button)
        self.status_label = QLabel("Status: Ready")
        bottom_layout.addWidget(self.status_label, 1) # Give it more space
        main_layout.addLayout(bottom_layout)

        self.validate_inputs() # Set initial state of the start button

    def select_root_folder(self):
        """
        Opens a dialog to select the root folder and then opens the
        folder selection dialog.
        """
        folder_path = QFileDialog.getExistingDirectory(self, "Select the Root Folder")
        if not folder_path:
            return

        self.root_folder_path = folder_path
        self.root_folder_label.setText(folder_path)

        try:
            # Find all subdirectories in the selected root folder
            subfolders = [d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, d))]
            subfolders.sort(key=natural_sort_key) # Use natural sorting

            if not subfolders:
                QMessageBox.information(self, "No Folders", "No sub-folders found in the selected directory.")
                self.selected_folders = []
                self.validate_inputs()
                return

            # Show the folder selection and ordering dialog
            dialog = FolderSelectionDialog(subfolders, self)
            if dialog.exec():
                # Get the full paths of the selected folders
                self.selected_folders = [os.path.join(self.root_folder_path, f) for f in dialog.get_selected_folders_in_order()]
                self.selected_folders_label.setText(f"Selected folders: {len(self.selected_folders)}")
            else:
                self.selected_folders = [] # User cancelled
                self.selected_folders_label.setText("Selected folders: 0")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read sub-folders: {e}")
            self.selected_folders = []

        self.validate_inputs()

    def select_output_file(self):
        """
        Opens a dialog to specify the save location for the output PDF.
        """
        filepath, _ = QFileDialog.getSaveFileName(self, "Specify Output PDF File", "", "PDF Files (*.pdf)")
        if filepath:
            self.output_path_label.setText(filepath)

    def validate_inputs(self):
        """
        Enable or disable the start button based on whether all necessary
        inputs have been provided.
        """
        is_valid = (
            bool(self.selected_folders) and
            "No file specified..." not in self.output_path_label.text()
        )
        self.start_button.setEnabled(is_valid)

    def start_processing(self):
        """
        Kicks off the PDF generation process in a background thread.
        """
        self.start_button.setEnabled(False)
        self.status_label.setText("Status: Starting...")

        output_path = self.output_path_label.text()

        # --- Setup and run worker thread ---
        self.worker = PdfWorker(self.selected_folders, output_path)
        self.thread = threading.Thread(target=self.worker.run)
        self.worker.signals.progress.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_processing_finished)
        self.thread.start()

    def update_status(self, message):
        """
        Updates the status label with progress from the worker thread.
        """
        self.status_label.setText(f"Status: {message}")
        print(message) # Also log to terminal for debugging

    def on_processing_finished(self, message):
        """
        Handles the completion signal from the worker thread.
        """
        if message.startswith("Error"):
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Status: Error!")
        else:
            QMessageBox.information(self, "Success", message)
            self.status_label.setText("Status: Ready")

        self.validate_inputs() # Re-enable the start button if inputs are still valid

    def closeEvent(self, event):
        """
        Ensure the worker thread is stopped gracefully if running when the
        application is closed.
        """
        if hasattr(self, 'worker') and self.thread.is_alive():
            self.worker.stop()
            self.thread.join()
        event.accept()

def main():
    """The main entry point of the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
