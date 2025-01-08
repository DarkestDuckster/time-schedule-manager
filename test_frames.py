from __future__ import annotations
import os
import numpy as np

class TimeFrame:

    def __init__(
        self,
        start: float,
        end: float,
        available: bool = False,
        ):
        duration = end - start

        self.start = start
        self.end = end
        self.available = available
        self.next = None
        self.prev = None

    def connectNext(self, other_frame: TimeFrame) -> None:
        self.next = other_frame
        other_frame.prev = self

    def hasNext(self) -> bool:
        has_next = self.next is not None
        return has_next

    def hasPrev(self) -> bool:
        has_prev = self.prev is not None
        return has_prev

    def getNext(self) -> TimeFrame:
        return self.next

    def timeInside(self, time: float) -> bool:
        return self.start <= time < self.end

    @property
    def duration(self) -> float:
        return self.end - self.start

    def findStart(self):
        cur_frame = self
        while cur_frame.hasPrev():
            cur_frame = cur_frame.prev
        return cur_frame

    def findEnd(self):
        cur_frame = self
        while cur_frame.hasNext():
            cur_frame = cur_frame.next
        return cur_frame

    def __str__(self):
        occ_sign = "+" if self.available else "-"
        return f"[{self.start},{self.end},{occ_sign}]"

class FrameContainer:

    def __init__(self, allocation_strategy = None):
        base_frame = TimeFrame(-float("inf"), float("inf"), True)
        if allocation_strategy is None:
            allocation_strategy = findAvailable
        self._start = base_frame
        self._end = base_frame
        self._allocation_strategy = allocation_strategy

    def findFrame(self, time: float) -> TimeFrame:
        cur_frame = self._start
        while not cur_frame.timeInside(time) and cur_frame.hasNext():
            cur_frame = cur_frame.getNext()
        return cur_frame

    def _findClosestBefore(self, time: float) -> TimeFrame:
        cur_frame = self._start
        while True:
            if cur_frame.next is None:
                break
            if not cur_frame.next.start < time:
                break
            cur_frame = cur_frame.next
        return cur_frame

    def _findClosestAfter(self, time: float) -> TimeFrame:
        cur_frame = self._end
        while True:
            if cur_frame.prev is None:
                break
            if not cur_frame.prev.end > time:
                break
            cur_frame = cur_frame.prev
        return cur_frame

    def _spliceInterval(
        self,
        interval: TimeFrame,
        start: float,
        end: float,
        available: bool,
        ) -> None:
        if interval.available == available:
            return
        pre_interval = TimeFrame(interval.start, start, not available)
        new_interval = TimeFrame(start, end, available)
        post_interval = TimeFrame(end, interval.end, not available)

        if interval.prev is not None:
            interval.prev.connectNext(pre_interval)
        if interval.next is not None:
            post_interval.connectNext(interval.next)

        pre_interval.connectNext(new_interval)
        new_interval.connectNext(post_interval)
        self._start = pre_interval.findStart()
        self._end = post_interval.findEnd()

    def _connectIntervals(
        self,
        interval_start: TimeFrame,
        interval_end: TimeFrame,
        start: float,
        end: float,
        available: bool,
        ) -> None:
        # Match for the four different cases and handle appropriately
        start_same = interval_start.available == available
        end_same = interval_end.available == available

        if start_same and end_same:
                interval_start.end = end
                interval_start.end = interval_end.end
                if interval_end.next is not None:
                    interval_start.connectNext(interval_end.next)
                else:
                    interval_start.next = None
                self._end = interval_start.findEnd()

        elif start_same and not end_same:
                interval_start.end = end
                interval_end.start = end
                interval_start.connectNext(interval_end)

        elif not start_same and end_same:
                interval_start.end = start
                interval_end.start = start
                interval_start.connectNext(interval_end)

        elif not start_same and not end_same:
                interval_start.end = start
                interval_end.start = end
                new_interval = TimeFrame(start, end, available)
                interval_start.connectNext(new_interval)
                new_interval.connectNext(interval_end)

    def occupyTime(
        self,
        start: float,
        end: float,
        available: bool = False,
        ) -> None:
        interval_start = self._findClosestBefore(start)
        interval_end = self._findClosestAfter(end)
        if interval_start is interval_end:
            self._spliceInterval(
                interval_start,
                start,
                end,
                available,
            )
        else:
            self._connectIntervals(
                interval_start,
                interval_end,
                start,
                end,
                available,
            )

    def _contingencyCheck(self):
        cur_frame = self._start
        while cur_frame is not self._end:
            assert cur_frame.next.start == cur_frame.end
            assert cur_frame.next.available != cur_frame.available
            cur_frame = cur_frame.next

    def printFrames(self):
        cur_frame = self._start
        frames_str = ""
        frames_str += str(cur_frame)
        while cur_frame is not self._end:
            cur_frame = cur_frame.next
            frames_str += str(cur_frame)
        print(frames_str)

    def showFrameHistory(
        self,
        time_start: float | None = None,
        time_end: float | None = None,
        text_width: int = 100,
        ) -> None:
        if not self._start.hasNext():
            print("Empty container")
            return

        text_width = os.get_terminal_size()[0] - 6
        if time_start is None:
            time_start = self._start.next.start
        if time_end is None:
            time_end = self._end.prev.end
        time_range = time_end - time_start

        time_chrs = [" "] * text_width
        cur_frame = self._start.next
        while cur_frame is not self._end:
            if cur_frame.available:
                cur_frame = cur_frame.next
                continue
            if cur_frame.start >= time_end:
                break
            start_offset = cur_frame.start - time_start
            start_idx = int(start_offset / time_range * len(time_chrs))
            end_offset = cur_frame.end - time_start
            end_idx = int(end_offset / time_range * len(time_chrs))
            frame_char_width = end_idx - start_idx
            time_chrs[start_idx:end_idx] = ["-"] * frame_char_width
            time_chrs[start_idx] = "|"
            time_chrs[end_idx - 1] = "|"
            cur_frame = cur_frame.next
        print(">>", "".join(time_chrs), "<<")

    def getAllocationStrategy(self):
        return self._allocation_strategy


class MultiContainer:

    def __init__(self, containers):
        self._containers = containers

    def addContainer(self, new_container):
        self._containers.append(new_container)

    def searchOpening(self, start, duration):
        proposed = TimeFrame(start, start + duration)
        original_proposal = TimeFrame(start, start + duration)
        modified_proposal = True

        while modified_proposal:
            modified_proposal = False
            for cont in self._containers:
                alloc_strat = cont.getAllocationStrategy()
                modified_proposal = alloc_strat(
                    cont,
                    proposed,
                    original_proposal,
                )
                if modified_proposal:
                    break
        return proposed

def obstructed(container, start, duration):
    frame = container.findFrame(start)
    if not frame.available:
        return True
    return frame.end - start < duration

def getNextOpening(container, start):
    frame = container.findFrame(start)
    if not frame.available:
        return frame.next.start
    return frame.next.next.start

def findAvailable(
    container,
    proposal,
    original_proposal,
    ):
    frame = container.findFrame(proposal.start)
    if frame.available:
        return False
    frame = frame.getNext()
    proposal.start = frame.start
    proposal.end = frame.start + original_proposal.duration
    return True

def findAvailableWithExtension(
    container,
    proposal,
    original_proposal,
    ):
    frame = container.findFrame(proposal.start)
    end_frame = container.findFrame(proposal.end)
    if frame.available and end_frame.available:
        return False

    if not frame.available:
        frame = frame.getNext()
        proposal.start = frame.start

    remaining_duration = original_proposal.duration

    while remaining_duration > frame.duration:
        remaining_duration -= frame.duration
        frame = frame.next.next

    end = frame.start + remaining_duration
    remaining_duration = 0

    proposal.end = end
    return True

def findClear(
    container,
    proposal,
    original_proposal,
    ):
    frame = container.findFrame(proposal.start)
    if frame.available and proposal.duration <= frame.end - proposal.start:
        return False

    frame = frame.next
    if not frame.available:
        frame = frame.next

    while original_proposal.duration > frame.duration:
        frame = frame.next.next

    proposal.start = frame.start
    proposal.end = frame.start + original_proposal.duration
    return True

def findSpecific(open_close_schedule, operation_schedule, use_schedule, start, duration):
    proposed = TimeFrame(start, start + duration)
    original_proposal = TimeFrame(start, duration)
    while True:
        proposed = findAvailable(open_close_schedule, proposed.start, proposed.duration)
        proposed = findAvailableWithExtension(operation_schedule, proposed.start, proposed.duration)
        if obstructed(use_schedule, proposed.start, proposed.duration):
            proposed.start = getNextOpening(container_b, start)
            continue
        return proposed


DAYS = 3
UNTIL = (DAYS) * 24
OPEN = 8
CLOSE = 20
CLOSE_OP = 24
open_closed_schedule = FrameContainer(findAvailable)
OP_schedule = FrameContainer(findAvailableWithExtension)
use_schedule = FrameContainer(findClear)
tmp_schedule = FrameContainer()
for day in range(DAYS):
    open_closed_schedule.occupyTime(day * 24, day * 24 + OPEN)
    open_closed_schedule.occupyTime(day * 24 + CLOSE, (day + 1) * 24)
    OP_schedule.occupyTime(day * 24, day * 24 + OPEN)
    OP_schedule.occupyTime(day * 24 + CLOSE_OP, (day + 1) * 24)

multi_cont = MultiContainer([open_closed_schedule, OP_schedule, use_schedule])
actual = multi_cont.searchOpening(8, 14)
use_schedule.occupyTime(actual.start, actual.end)
actual = multi_cont.searchOpening(34, 3)
use_schedule.occupyTime(actual.start, actual.end)
actual = multi_cont.searchOpening(9, 3)
tmp_schedule.occupyTime(actual.start, actual.end)

open_closed_schedule.showFrameHistory(0, UNTIL)
OP_schedule.showFrameHistory(0, UNTIL)
use_schedule.showFrameHistory(0, UNTIL)
tmp_schedule.showFrameHistory(0, UNTIL)
