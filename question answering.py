import os
from openai import OpenAI

# 配置 DeepSeek API
client = OpenAI(
    api_key="sk-423a2d8c08b143ad88363249d2681f1c",  # 从环境变量读取 API 密钥
    base_url="https://api.deepseek.com/v1"  # DeepSeek 的 API 地址
)
model = "deepseek-chat"  # DeepSeek 的模型名称

def Question_Answer():
    print("DeepSeek 智能问答系统 (输入 '退出' 或 'exit' 结束)")
    
    # 存储对话历史
    conversation_history = []
    
    while True:
        user_input = input("\n[您]: ")
        
        # 退出条件
        if user_input.lower() in ["退出", "exit"]:
            print("对话结束")
            break
        
        # 添加用户消息到历史
        conversation_history.append({"role": "user", "content": user_input})
        
        try:
            # 调用 DeepSeek API（新版本语法）
            response = client.chat.completions.create(
                model=model,
                messages=conversation_history,
                stream=False
            )
            
            # 获取 AI 回复
            ai_reply = response.choices[0].message.content
            
            # 添加 AI 回复到历史
            conversation_history.append({"role": "assistant", "content": ai_reply})
            
            print(f"\n[AI]: {ai_reply}")
            
        except Exception as e:
            print(f"发生错误: {str(e)}")
            # 移除最后一条用户输入（如果出错）
            if conversation_history and conversation_history[-1]["role"] == "user":
                conversation_history.pop()

if __name__ == "__main__":
    Question_Answer()