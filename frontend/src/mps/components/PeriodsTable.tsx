import { useCallback, useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { Alert } from '../../components/Alert';
import { RenderItemProps, SortableList } from '../../components/SortableList';

import { MultiPeriodModelContext } from '../../hooks/useMultiPeriodStream';
import { AppStateContext } from "../../appState";
import { MpsPeriod } from "../../types/MpsPeriod";
import { GuestPeriodRow } from "./GuestPeriodRow";
import { PeriodRow } from "./PeriodRow";

interface ButtonToolbarProps {
  onAddPeriod: (ev: Event) => void;
}

function ButtonToolbar({ onAddPeriod }: ButtonToolbarProps) {
  const { user } = useContext(AppStateContext);
  if (!user.value.permissions.media) {
    return null;
  }
  return <div className="btn-toolbar">
    <button className="btn btn-primary btn-sm m-2" onClick={onAddPeriod}>
      Add a Period
    </button>
  </div>;
}

export function PeriodsTable() {
  const { user } = useContext(AppStateContext);
  const { errors, model, addPeriod, setPeriodOrdering } = useContext(
    MultiPeriodModelContext
  );
  const periods = useComputed<MpsPeriod[]>(() => model.value?.periods ?? []);
  const errorList = useComputed<string[]>(() => {
    const errs: string[] = Object.entries(errors.value.periods ?? []).map(([pid, err]) => {
      return `${pid}: ${Object.values(err).join(". ")}`;
    });
    if (errors.value.allPeriods) {
      errs.push(errors.value.allPeriods);
    }
    return errs;
  });

  const setPeriodOrder = useCallback(
    (items: MpsPeriod[]) => {
      const pks = items.map((prd: MpsPeriod) => prd.pk);
      setPeriodOrdering(pks);
    },
    [setPeriodOrdering]
  );

  const addPeriodBtn = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      addPeriod();
    },
    [addPeriod]
  );

  const renderItem = useCallback(
    ({item, ...props}: RenderItemProps) => {
      const row = item as MpsPeriod;
      if (!user.value.permissions.media) {
        return <GuestPeriodRow {...props} item={row} />;
      }
      return <PeriodRow {...props} item={row} />;
    },
    [user.value.permissions.media]
  );

  return <div>
    <div className="period-table border">
      <div className="row bg-secondary text-white table-head">
        <div className="col period-ordering">#</div>
        <div className="col period-id">ID</div>
        <div className="col period-stream">Stream</div>
        <div className="col period-start">Start Time</div>
        <div className="col period-duration">Duration</div>
        <div className="col period-tracks">Tracks</div>
      </div>
      <SortableList
        items={periods}
        setItems={setPeriodOrder}
        RenderItem={renderItem}
        dataKey="pk"
      />
      <ButtonToolbar onAddPeriod={addPeriodBtn} />
    </div>
    {errorList.value.map(
      (err: string, index: number) => <Alert id={index} key={err} text={err} level="warning" />
    )}
  </div>;
}
