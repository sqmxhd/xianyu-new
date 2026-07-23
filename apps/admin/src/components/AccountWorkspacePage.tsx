import { Button, Empty, Select, Space, Typography } from "antd";
import type { ReactNode } from "react";

import type { Account } from "../types";

const { Text } = Typography;

interface AccountWorkspacePageProps {
  accounts: Account[];
  selectedAccount: Account | null;
  title: string;
  emptyDescription: string;
  refreshText: string;
  loading: boolean;
  onSelect: (account: Account) => void;
  onRefresh: () => void;
  extraActions?: ReactNode;
  children: ReactNode;
}

export function AccountWorkspacePage({
  accounts,
  selectedAccount,
  title,
  emptyDescription,
  refreshText,
  loading,
  onSelect,
  onRefresh,
  extraActions,
  children
}: AccountWorkspacePageProps) {
  return (
    <Space direction="vertical" size={16} className="content-stack">
      <div className="workspace-toolbar">
        <Space wrap>
          <Text strong>当前账户</Text>
          <Select
            className="account-selector"
            placeholder="选择账户"
            value={selectedAccount?.account_id}
            options={accounts.map((account) => ({
              label: account.account_name,
              value: account.account_id
            }))}
            onChange={(accountId) => {
              const account = accounts.find((item) => item.account_id === accountId);
              if (account) {
                onSelect(account);
              }
            }}
          />
          <Button disabled={!selectedAccount} loading={loading} onClick={onRefresh}>
            {refreshText}
          </Button>
          {extraActions}
        </Space>
      </div>
      {selectedAccount ? (
        <section className="workspace-content" aria-label={`${title}：${selectedAccount.account_name}`}>
          {children}
        </section>
      ) : (
        <div className="workspace-empty">
          <Empty description={emptyDescription} />
        </div>
      )}
    </Space>
  );
}
