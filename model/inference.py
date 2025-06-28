# inference.py
import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
from PIL import Image
import sys
import torch.nn.functional as F
import json
import random

k = 512
m = 23

class G_Stream_net(nn.Module):
    def __init__(self, conv1_conv4, conv5, num_classes=23):
        super(G_Stream_net, self).__init__()
        self.conv1_conv4 = conv1_conv4
        self.conv5 = conv5 
        self.fc = nn.Sequential(
            nn.Linear(512 * 7 * 7, 4096),
            nn.ReLU(True),
            nn.Dropout(0.5),
            nn.Linear(4096, 4096),
            nn.ReLU(True),
            nn.Dropout(0.5),
            nn.Linear(4096, num_classes),
        )
        
    def forward(self, x):
        out = self.conv1_conv4(x)
        out = self.conv5(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out

class P_Stream_net(nn.Module):
    def __init__(self, conv1_conv4):
        super(P_Stream_net, self).__init__()
        self.conv1_conv4 = conv1_conv4
        self.conv6 = nn.Conv2d(512, k*m, kernel_size=1, stride=1, padding=0)
        self.pool6 = nn.MaxPool2d((28, 28), stride=(28, 28))
        self.fc = nn.Linear(k*m, m)
        
    def forward(self, x):
        out = self.conv1_conv4(x)
        out = self.conv6(out)
        out = self.pool6(out)
        out = F.normalize(out, p=2, dim=1)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out

class Side_Branch_net(nn.Module):
    def __init__(self, conv1_conv4):
        super(Side_Branch_net, self).__init__()
        self.conv1_conv4 = conv1_conv4
        self.conv6 = nn.Conv2d(512, k*m, kernel_size=1, stride=1, padding=0)
        self.pool6 = nn.MaxPool2d((28, 28), stride=(28, 28))
        self.avgpool = nn.AdaptiveAvgPool1d(1)
        
    def forward(self, x):
        out = self.conv1_conv4(x)
        out = self.conv6(out)
        out = self.pool6(out)
        N = out.size(0)
        out = out.view(N, -1)
        out = out.view(N, m, k)
        out = self.avgpool(out)
        out = F.normalize(out, p=2, dim=1)
        out = out.view(N, -1)
        return out

# 图像预处理
def load_and_preprocess(image_path):
    transform = transforms.Compose([
        transforms.Resize(256),          # 调整图像大小
        transforms.CenterCrop(224),      # 中心裁剪
        transforms.ToTensor(),           # 转为Tensor
        transforms.Normalize(            # 标准化 (使用ImageNet均值方差)
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    image = Image.open(image_path).convert('RGB')
    return transform(image).unsqueeze(0)  # 添加batch维度

def generate_fish_length(class_name):
    # 加载体长范围数据
    with open('./model/fish_length_ranges.json') as f:
        length_ranges = json.load(f)
    
    min_length, max_length = length_ranges[class_name]
    # 生成范围内的随机体长（厘米）
    return random.randint(min_length, max_length)

def predict(image_path):
    # 参数解析
    model_path = "./model/best_model.pth"

    # 检查GPU可用性
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 加载预训练VGG16基础
    vgg16 = torchvision.models.vgg16(weights=torchvision.models.VGG16_Weights.DEFAULT)
    conv1_conv4 = torch.nn.Sequential(*list(vgg16.features.children())[:-8])
    conv5 = torch.nn.Sequential(*list(vgg16.features.children())[-8:])
    
    # 初始化模型
    g_stream = G_Stream_net(conv1_conv4, conv5).to(device)
    p_stream = P_Stream_net(conv1_conv4).to(device)
    side_branch = Side_Branch_net(conv1_conv4).to(device)
    
    # 加载训练好的权重
    checkpoint = torch.load(model_path, map_location=device)
    g_stream.load_state_dict(checkpoint['g_stream_state_dict'])
    p_stream.load_state_dict(checkpoint['p_stream_state_dict'])
    side_branch.load_state_dict(checkpoint['side_branch_state_dict'])
    
    # 设置评估模式
    g_stream.eval()
    p_stream.eval()
    side_branch.eval()
    
    # 加载并预处理图像
    image_tensor = load_and_preprocess(image_path).to(device)
    
    # 执行推理
    with torch.no_grad():
        out_g = g_stream(image_tensor)
        out_p = p_stream(image_tensor)
        out_s = side_branch(image_tensor)
        
        # 融合输出（使用训练时的权重）
        fused = 0.6 * out_g + 0.3 * out_p + 0.1 * out_s
        
        # 获取预测类别
        _, predicted = torch.max(fused, 1)
        class_idx = predicted.item()
    
    with open("./model/class_to_idx.json", 'r') as f:
        class_to_idx = json.load(f)
    
    # 创建索引到类别的反向映射
    idx_to_class = {idx: class_name for class_name, idx in class_to_idx.items()}
    class_name = idx_to_class[class_idx]
    print(f"Predicted class index: {class_name}")
    predicted_length = generate_fish_length(class_name)
    print(f"Predicted length: {predicted_length} cm")

    return class_name, predicted_length
    


if __name__ == '__main__':
    predict()