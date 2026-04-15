import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { LockOutlined, SafetyOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const res = await authAPI.login(values.token);
      localStorage.setItem('access_token', res.data.access_token);
      message.success('Login successful');
      navigate('/dashboard');
    } catch (err) {
      message.error(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-logo">
          <SafetyOutlined style={{ fontSize: 48, color: '#0050b3' }} />
          <div className="login-logo-text">FBI IC3 Admin</div>
        </div>
        <div className="login-subtitle">Multi-Channel Management Platform</div>
        <Form name="login" onFinish={onFinish} size="large">
          <Form.Item name="token" rules={[{ required: true, message: 'Please input admin token!' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Admin Token" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>Login</Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center', color: '#00000073', fontSize: 12 }}>
          <p>FBI IC3 - Internet Crime Complaint Center</p>
          <p>Authorized Personnel Only</p>
        </div>
      </div>
    </div>
  );
}

export default Login;
