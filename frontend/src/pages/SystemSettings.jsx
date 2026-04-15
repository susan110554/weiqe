import { useState, useEffect } from 'react';
import { Card, Form, Input, Switch, Button, message, Divider, Row, Col, Select, Tabs } from 'antd';
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import { systemAPI } from '../services/api';

const { Option } = Select;

function SystemSettings() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [lang, setLang] = useState(localStorage.getItem('ui_lang') || 'zh');

  const fetch = () => {
    setLoading(true);
    systemAPI.getConfig()
      .then(r => {
        const cfg = r.data.configs || {};
        form.setFieldsValue({
          bot_token_masked: cfg.bot_token ? '****' + cfg.bot_token.slice(-4) : '',
          maintenance_mode: cfg.maintenance_mode === 'true',
          registration_enabled: cfg.registration_enabled !== 'false',
          free_daily_quota: cfg.free_daily_quota || '5',
          paid_daily_quota: cfg.paid_daily_quota || '50',
          max_address_monitor: cfg.max_address_monitor || '10',
          smtp_host: cfg.smtp_host || '',
          smtp_port: cfg.smtp_port || '587',
          smtp_from: cfg.smtp_from || '',
          admin_ip_whitelist: cfg.admin_ip_whitelist || '',
          session_timeout: cfg.session_timeout || '480',
        });
      })
      .catch(() => message.error('加载配置失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, []);

  const handleSave = async (values) => {
    setSaving(true);
    const configs = {
      maintenance_mode: String(values.maintenance_mode),
      registration_enabled: String(values.registration_enabled),
      free_daily_quota: String(values.free_daily_quota),
      paid_daily_quota: String(values.paid_daily_quota),
      max_address_monitor: String(values.max_address_monitor),
      smtp_host: values.smtp_host || '',
      smtp_port: String(values.smtp_port || ''),
      smtp_from: values.smtp_from || '',
      admin_ip_whitelist: values.admin_ip_whitelist || '',
      session_timeout: String(values.session_timeout || '480'),
    };
    try {
      await systemAPI.updateConfig(configs);
      message.success('设置已保存');
    } catch { message.error('保存失败'); }
    finally { setSaving(false); }
  };

  const handleLangChange = (v) => {
    setLang(v);
    localStorage.setItem('ui_lang', v);
    message.success(v === 'zh' ? '已切换为中文' : '已切换为英文');
  };

  const tabItems = [
    {
      key: 'basic', label: '基础设置',
      children: (
        <>
          <Form.Item label="界面语言">
            <Select value={lang} onChange={handleLangChange} style={{ width: 200 }}>
              <Option value="zh">中文</Option>
              <Option value="en">English</Option>
            </Select>
          </Form.Item>
          <Form.Item label="机器人 Token" name="bot_token_masked" extra="出于安全考虑已隐藏">
            <Input disabled />
          </Form.Item>
          <Form.Item label="维护模式" name="maintenance_mode" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="允许注册" name="registration_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      )
    },
    {
      key: 'quota', label: '配额设置',
      children: (
        <>
          <Form.Item label="免费用户每日配额" name="free_daily_quota"><Input type="number" /></Form.Item>
          <Form.Item label="付费用户每日配额" name="paid_daily_quota"><Input type="number" /></Form.Item>
          <Form.Item label="最大地址监控数" name="max_address_monitor"><Input type="number" /></Form.Item>
        </>
      )
    },
    {
      key: 'email', label: '邮件 (SMTP)',
      children: (
        <>
          <Form.Item label="SMTP 主机" name="smtp_host"><Input placeholder="smtp.example.com" /></Form.Item>
          <Form.Item label="SMTP 端口" name="smtp_port"><Input type="number" /></Form.Item>
          <Form.Item label="发件邮箱" name="smtp_from"><Input placeholder="noreply@fbi-ic3.gov" /></Form.Item>
        </>
      )
    },
    {
      key: 'security', label: '安全设置',
      children: (
        <>
          <Form.Item label="管理员 IP 白名单" name="admin_ip_whitelist" extra="逗号分隔的IP列表，留空表示允许所有IP">
            <Input placeholder="192.168.1.1, 10.0.0.1" />
          </Form.Item>
          <Form.Item label="会话超时 (分钟)" name="session_timeout"><Input type="number" /></Form.Item>
        </>
      )
    },
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">系统设置</h1></div>
      <div className="content-wrapper">
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Tabs items={tabItems} />
          <Divider />
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>保存设置</Button>
            <Button icon={<ReloadOutlined />} onClick={fetch} style={{ marginLeft: 8 }}>重置</Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
}

export default SystemSettings;
