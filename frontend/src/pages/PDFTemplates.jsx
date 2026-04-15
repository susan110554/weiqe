import { useState, useEffect } from 'react';
import { Table, Button, Space, message, Modal, Form, Input } from 'antd';
import { EditOutlined, ReloadOutlined } from '@ant-design/icons';
import { pdfAPI } from '../services/api';

const { TextArea } = Input;

function PDFTemplates() {
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  const fetch = () => {
    setLoading(true);
    pdfAPI.getAll()
      .then(r => setTemplates(r.data.templates || []))
      .catch(() => message.error('加载PDF模板失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, []);

  const handleEdit = (rec) => {
    setEditing(rec);
    form.setFieldsValue({ html_content: rec.html_content, css_content: rec.css_content });
    setModalVisible(true);
  };

  const handleSubmit = async (values) => {
    try {
      await pdfAPI.update(editing.template_name, values);
      message.success('PDF模板已更新');
      setModalVisible(false);
      fetch();
    } catch (e) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const cols = [
    { title: '模板名称', dataIndex: 'template_name', key: 'template_name' },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
    { title: '版本', dataIndex: 'version', key: 'version' },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(r)}>编辑</Button>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">PDF模板</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
        </div>
        <Table dataSource={templates} columns={cols} loading={loading} rowKey="template_name" pagination={false} />
      </div>

      <Modal
        title={`编辑PDF模板: ${editing?.template_name || ''}`}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={800}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item label="HTML内容" name="html_content" rules={[{ required: true }]}>
            <TextArea rows={12} style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
          <Form.Item label="CSS内容" name="css_content">
            <TextArea rows={6} style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default PDFTemplates;
