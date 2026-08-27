import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()

nb.cells.extend([
    new_markdown_cell("# AcademiQ ML Proctoring - Model Training Pipeline\n\nThis notebook trains and compares multiple models (MobileNetV2, ResNet18, EfficientNetB0) for Head Pose Estimation to determine the best performer for deployment. It uses the 300W-LP dataset."),
    
    new_markdown_cell("## 1. Setup & Dependencies"),
    new_code_cell("""!pip install -q mediapipe onnx onnxruntime
import os
import cv2
import numpy as np
import scipy.io as sio
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
import matplotlib.pyplot as plt
from tqdm.auto import tqdm"""),

    new_markdown_cell("## 2. Mount Google Drive\n\nWe mount drive to save the dataset to ephemeral storage and the final `.onnx` models permanently to your Drive."),
    new_code_cell("""from google.colab import drive
drive.mount('/content/drive')

DRIVE_DIR = '/content/drive/MyDrive/AcademiQ_ML'
os.makedirs(DRIVE_DIR, exist_ok=True)
os.makedirs(os.path.join(DRIVE_DIR, 'results', 'loss'), exist_ok=True)
os.makedirs(os.path.join(DRIVE_DIR, 'results', 'visualization'), exist_ok=True)"""),

    new_markdown_cell("## 3. Dataset Download (300W-LP)"),
    new_code_cell("""# Note: 300W-LP is usually downloaded via a specific gdown link or uploaded directly.
# Replace this with the actual gdown ID if you have a public mirror, or upload the zip to your drive manually.
# Example: !gdown --id <PUBLIC_FILE_ID> -O 300W_LP.zip
# !unzip -q 300W_LP.zip -d /content/data

print("Please ensure the 300W-LP dataset is extracted to /content/data/300W_LP")
DATA_DIR = '/content/data/300W_LP'"""),

    new_markdown_cell("## 4. PyTorch Dataset Definition"),
    new_code_cell("""class HeadPoseDataset(Dataset):
    def __init__(self, data_dir, transform=None):
        self.data_dir = data_dir
        self.transform = transform
        self.image_paths = []
        self.labels = []
        
        # Placeholder for dataset loading logic
        # For a real implementation, you would walk through DATA_DIR, 
        # pair .jpg files with .mat files, extract yaw, pitch, roll using scipy.io.loadmat,
        # crop the face using MediaPipe, and append to these lists.
        
        # Simulated dummy data for compilation testing
        for i in range(100):
            self.image_paths.append(f"dummy_{i}.jpg")
            self.labels.append(np.array([0.0, 0.0, 0.0], dtype=np.float32))
            
    def __len__(self):
        return len(self.image_paths)
        
    def __getitem__(self, idx):
        # Simulated loading
        img = Image.fromarray(np.uint8(np.random.rand(224, 224, 3) * 255))
        label = self.labels[idx]
        
        if self.transform:
            img = self.transform(img)
            
        return img, torch.tensor(label)

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

dataset = HeadPoseDataset(DATA_DIR, transform=transform)
train_size = int(0.8 * len(dataset))
val_size = len(dataset) - train_size
train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)"""),

    new_markdown_cell("## 5. Model Definitions (MobileNetV2, ResNet18, EfficientNet)"),
    new_code_cell("""def get_mobilenet_v2():
    model = models.mobilenet_v2(pretrained=True)
    model.classifier[1] = nn.Linear(model.last_channel, 3) # yaw, pitch, roll
    return model

def get_resnet18():
    model = models.resnet18(pretrained=True)
    model.fc = nn.Linear(model.fc.in_features, 3)
    return model

def get_efficientnet_b0():
    model = models.efficientnet_b0(pretrained=True)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 3)
    return model"""),

    new_markdown_cell("## 6. Training Loop"),
    new_code_cell("""def train_model(model, name, epochs=5):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    
    train_losses = []
    val_losses = []
    
    print(f"--- Training {name} ---")
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for inputs, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs} (Train)"):
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            
        train_loss = running_loss / len(train_loader)
        train_losses.append(train_loss)
        
        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for inputs, labels in tqdm(val_loader, desc=f"Epoch {epoch+1}/{epochs} (Val)"):
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                
        val_loss /= len(val_loader)
        val_losses.append(val_loss)
        
        print(f"Epoch {epoch+1} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
    # Plot and save loss curves
    plt.figure()
    plt.plot(train_losses, label='Train')
    plt.plot(val_losses, label='Validation')
    plt.title(f"{name} Loss Curve")
    plt.legend()
    plt.savefig(os.path.join(DRIVE_DIR, 'results', 'loss', f'{name}_loss.png'))
    plt.close()
    
    return model, val_losses[-1]

# In a real run, you would increase epochs.
models_to_test = {
    "MobileNetV2": get_mobilenet_v2(),
    "ResNet18": get_resnet18(),
    "EfficientNetB0": get_efficientnet_b0()
}

best_loss = float('inf')
best_name = None
best_model = None

for name, model in models_to_test.items():
    trained_model, final_val_loss = train_model(model, name, epochs=2)
    if final_val_loss < best_loss:
        best_loss = final_val_loss
        best_name = name
        best_model = trained_model

print(f"Best Model: {best_name} with Val Loss: {best_loss:.4f}")"""),

    new_markdown_cell("## 7. Export Best Model to ONNX"),
    new_code_cell("""# Export the best model to ONNX for CPU-optimized FastAPI inference
best_model.eval()
best_model.to('cpu')
dummy_input = torch.randn(1, 3, 224, 224)

onnx_path = os.path.join(DRIVE_DIR, 'best_head_pose.onnx')
torch.onnx.export(
    best_model, 
    dummy_input, 
    onnx_path, 
    export_params=True, 
    opset_version=12,
    input_names=['input'], 
    output_names=['output'],
    dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
)

print(f"Successfully exported {best_name} to {onnx_path}!")
print("Download this .onnx file and place it in ml-service/app/model/head_pose.onnx")""")
])

with open('/Users/sagnikchandra/Documents/Projects/Web/AcademiQ/ml-service/training/Proctoring_Model_Training.ipynb', 'w') as f:
    nbformat.write(nb, f)
print("Notebook generated successfully!")
