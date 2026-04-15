import { useState, useEffect } from 'react';
import { Table, Button, Select, Space, Tag, message, Modal, Form, Input } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { templatesAPI } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

function Templates() {
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [channel, setChannel] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  const fetch = () => {
    setLoading(true);
    templatesAPI.getAll(channel)
      .then(r => setTemplates(r.data.templates || []))
      .catch(() => message.error('加载模板失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [channel]);

  const handleEdit = (rec) => { setEditing(rec); form.setFieldsValue(rec); setModalVisible(true); };
  const handleCreate = () => { setEditing(null); form.resetFields(); setModalVisible(true); };
  const handleDelete = (key, ch) => Modal.confirm({
    title: '确认删除',
    content: `确定删除 "${key}" 模板 (${ch})?`,
    onOk: () => templatesAPI.delete(key, ch).then(() => { message.success('已删除'); fetch(); }).catch(() => message.error('操作失败')),
  });

  const handleSubmit = async (values) => {
    try {
      if (editing) { await templatesAPI.update(editing.template_key, values); message.success('已更新'); }
      else { await templatesAPI.create(values); message.success('已创建'); }
      setModalVisible(false); fetch();
    } catch (e) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const cols = [
    { title: '模板键名', dataIndex: 'template_key', key: 'template_key' },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: v => <Tag color="blue">{v}</Tag> },
    { title: '类型', dataIndex: 'content_type', key: 'content_type' },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Space>
        <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(r)}>编辑</Button>
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.template_key, r.channel)}>删除</Button>
      </Space>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">模板管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Select placeholder="按渠道筛选" style={{ width: 200 }} allowClear onChange={setChannel}>
              <Option value="telegram">Telegram</Option>
              <Option value="whatsapp">WhatsApp</Option>
              <Option value="web">Web</Option>
              <Option value="default">Default</Option>
            </Select>
            <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => templatesAPI.refreshCache().then(() => message.success('缓存已刷新')).catch(() => message.error('操作失败'))}>刷新缓存</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>创建模板</Button>
          </Space>
        </div>
        <Table dataSource={templates} columns={cols} loading={loading} rowKey={r => `${r.template_key}_${r.channel}`} pagination={{ pageSize: 10 }} />
      </div>

      <Modal title={editing ? '编辑模板' : '创建模板'} open={modalVisible} onCancel={() => setModalVisible(false)} onOk={() => form.submit()} width={600}>
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          {!editing && <Form.Item label="模板键名" name="template_key" rules={[{ required: true }]}><Input /></Form.Item>}
          <Form.Item label="渠道" name="channel" rules={[{ required: true }]}>
            <Select><Option value="telegram">Telegram</Option><Option value="whatsapp">WhatsApp</Option><Option value="web">Web</Option><Option value="default">Default</Option></Select>
          </Form.Item>
          <Form.Item label="内容类型" name="content_type" initialValue="text">
            <Select><Option value="text">文本</Option><Option value="html">HTML</Option><Option value="markdown">Markdown</Option></Select>
          </Form.Item>
          <Form.Item label="标题" name="title"><Input /></Form.Item>
          <Form.Item label="内容" name="content" rules={[{ required: true }]}><TextArea rows={6} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Templates;
