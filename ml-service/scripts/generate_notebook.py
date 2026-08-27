import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()

nb.cells.extend([
    new_markdown_cell("# AcademiQ ML Proctoring - Model Training Pipeline\n\nThis notebook trains and compares multiple models (MobileNetV2, ResNet18, EfficientNetB0) for Head Pose Estimation to determine the best performer for deployment. It uses the 300W-LP dataset."),
    
    new_markdown_cell("## 1. Setup & Dependencies"),
    new_code_cell("""!pip install -q mediapipe onnx onnxruntime onnxscript
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

    new_markdown_cell("## 3. Dataset Download (AFLW2000-3D)\n\nWe will use the AFLW2000-3D dataset, which contains 2000 high-quality images with precise 3D face and pose annotations. This is an excellent, reliable dataset for real-world head pose estimation."),
    new_code_cell("""import zipfile
import os

dataset_url = "http://www.cbsr.ia.ac.cn/users/xiangyuzhu/projects/3DDFA/Database/AFLW2000-3D.zip"
zip_path = "/content/AFLW2000-3D.zip"
data_dir = "/content/data/AFLW2000"

if not os.path.exists(data_dir):
    print("Downloading AFLW2000-3D dataset (this may take a minute)...")
    # Using wget with a browser User-Agent because the server blocks default Python urllib requests
    !wget -U "Mozilla/5.0" -qO $zip_path $dataset_url
    
    print("Extracting dataset...")
    os.makedirs("/content/data", exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("/content/data")
    print("Dataset ready!")
else:
    print("Dataset already exists!")

DATA_DIR = data_dir"""),

    new_markdown_cell("## 4. PyTorch Dataset Definition"),
    new_code_cell("""class HeadPoseDataset(Dataset):
    def __init__(self, data_dir, transform=None):
        self.data_dir = data_dir
        self.transform = transform
        self.image_paths = []
        self.labels = []
        
        print(f"Scanning {data_dir} for .jpg and .mat pairs...")
        if not os.path.exists(data_dir):
            print(f"WARNING: Directory {data_dir} not found. Generating dummy data for testing.")
            for i in range(100):
                self.image_paths.append(f"dummy_{i}")
                self.labels.append(np.array([0.0, 0.0, 0.0], dtype=np.float32))
            return
            
        # Walk through dataset directory finding image and mat pairs
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith('.jpg'):
                    base_name = file[:-4]
                    mat_file = base_name + '.mat'
                    mat_path = os.path.join(root, mat_file)
                    img_path = os.path.join(root, file)
                    
                    if os.path.exists(mat_path):
                        try:
                            # 300W-LP / AFLW2000 format
                            mat_data = sio.loadmat(mat_path)
                            pose_para = mat_data['Pose_Para'][0][:3] # pitch, yaw, roll
                            # Convert to yaw, pitch, roll to match our inference engine
                            pitch, yaw, roll = pose_para[0], pose_para[1], pose_para[2]
                            
                            self.image_paths.append(img_path)
                            self.labels.append(np.array([yaw, pitch, roll], dtype=np.float32))
                        except Exception as e:
                            continue
                            
        print(f"Found {len(self.image_paths)} valid face images with pose labels.")
            
    def __len__(self):
        return len(self.image_paths)
        
    def __getitem__(self, idx):
        path = self.image_paths[idx]
        label = self.labels[idx]
        
        if path.startswith("dummy_"):
            img = Image.fromarray(np.uint8(np.random.rand(224, 224, 3) * 255))
        else:
            img = Image.open(path).convert('RGB')
        
        if self.transform:
            img = self.transform(img)
            
        return img, torch.tensor(label)

# Data Augmentation for real-world robustness
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1), # Simulate varying webcam lighting
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Load full dataset without transforms, then split, then apply transforms
full_dataset = HeadPoseDataset(DATA_DIR, transform=None)

train_size = int(0.8 * len(full_dataset))
val_size = len(full_dataset) - train_size
train_subset, val_subset = torch.utils.data.random_split(full_dataset, [train_size, val_size])

# Apply respective transforms
train_subset.dataset.transform = train_transform
val_subset.dataset.transform = val_transform

train_loader = DataLoader(train_subset, batch_size=32, shuffle=True)
val_loader = DataLoader(val_subset, batch_size=32, shuffle=False)"""),

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

# Train for 20 epochs for high-quality convergence
for name, model in models_to_test.items():
    trained_model, final_val_loss = train_model(model, name, epochs=20)
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
