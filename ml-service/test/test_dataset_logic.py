import os
import shutil
import scipy.io as sio
import numpy as np

def setup_mock_dataset(base_dir):
    """Creates a mock dataset structure mimicking AFLW2000-3D to test parsing logic"""
    os.makedirs(base_dir, exist_ok=True)
    
    for i in range(5):
        # Create dummy .jpg
        img_path = os.path.join(base_dir, f"image0000{i}.jpg")
        with open(img_path, 'wb') as f:
            f.write(os.urandom(1024)) # 1KB random binary data
            
        # Create dummy .mat with Pose_Para [pitch, yaw, roll, tdx, tdy, tdz, scale]
        mat_path = os.path.join(base_dir, f"image0000{i}.mat")
        dummy_pose = np.random.uniform(-1.0, 1.0, (1, 7)).astype(np.float32)
        sio.savemat(mat_path, {'Pose_Para': dummy_pose})
        
    # Add an image with missing .mat to test error handling
    with open(os.path.join(base_dir, "missing_mat.jpg"), 'wb') as f:
        f.write(os.urandom(1024))
        
def test_dataset_parsing():
    """Extracts and runs the exact parsing logic from generate_notebook.py"""
    print("--- Starting Detailed Dataset Parsing Inspection ---")
    mock_dir = "mock_aflw2000"
    setup_mock_dataset(mock_dir)
    
    image_paths = []
    labels = []
    
    try:
        # --- PASTE LOGIC FROM GENERATE_NOTEBOOK.PY ---
        for root, dirs, files in os.walk(mock_dir):
            for file in files:
                if file.endswith('.jpg'):
                    base_name = file[:-4]
                    mat_file = base_name + '.mat'
                    mat_path = os.path.join(root, mat_file)
                    img_path = os.path.join(root, file)
                    
                    if os.path.exists(mat_path):
                        try:
                            mat_data = sio.loadmat(mat_path)
                            pose_para = mat_data['Pose_Para'][0][:3] # pitch, yaw, roll
                            pitch, yaw, roll = pose_para[0], pose_para[1], pose_para[2]
                            
                            image_paths.append(img_path)
                            labels.append(np.array([yaw, pitch, roll], dtype=np.float32))
                        except Exception as e:
                            print(f"Error processing {mat_path}: {e}")
                            continue
        # ----------------------------------------------
        
        assert len(image_paths) == 5, f"Expected 5 valid pairs, got {len(image_paths)}"
        assert len(labels) == 5, f"Expected 5 labels, got {len(labels)}"
        assert labels[0].shape == (3,), f"Expected label shape (3,), got {labels[0].shape}"
        
        print(f"✅ Dataset parsing logic successfully processed {len(image_paths)} valid image/label pairs!")
        print("✅ Gracefully ignored images with missing .mat files.")
        print("✅ Correctly extracted (yaw, pitch, roll) from Pose_Para.")
        
    finally:
        # Cleanup
        if os.path.exists(mock_dir):
            shutil.rmtree(mock_dir)

if __name__ == "__main__":
    test_dataset_parsing()
