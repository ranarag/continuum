import os
import numpy as np
import torch
from torch.utils.data import DataLoader

from continuum.datasets import InMemoryDataset, H5Dataset
from continuum.scenarios import ContinualScenario
from continuum.tasks import TaskType


def create_subscenario(base_scenario, task_indexes):
    """
    In this function we want to create a subscenario from the different tasks, either by subsampling tasks or reodering
    or both.
    """

    if torch.is_tensor(task_indexes):
        task_indexes = task_indexes.numpy()

    new_x, new_y, new_t = None, None, None
    if base_scenario.cl_dataset.bounding_boxes is not None:
        raise ValueError("the function create_subscenario is not compatible with scenario with bounding_boxes yet.")

    for i, index in enumerate(task_indexes):
        taskset = base_scenario[index]
        all_task_indexes = np.arange(len(taskset))
        x, y, t = taskset.get_raw_samples(all_task_indexes)
        t = np.ones(len(y)) * i
        if new_x is None:
            new_x = x
            new_y = y
            new_t = t
        else:
            new_x = np.concatenate([new_x, x], axis=0)
            new_y = np.concatenate([new_y, y], axis=0)
            new_t = np.concatenate([new_t, t], axis=0)
    dataset = InMemoryDataset(new_x, new_y, new_t, data_type=base_scenario.cl_dataset.data_type)

    return ContinualScenario(dataset, transformations=base_scenario.transformations)


@torch.no_grad()
def encode_into_dataset(model, scenario, batch_size, filename, train):
    # we save feature in eval mode
    model.eval()

    encoded_dataset = None
    for task_id, taskset in enumerate(scenario):
        # we need to load the data to use the transformation if there is some
        loader = DataLoader(taskset, shuffle=False, batch_size=batch_size)
        for i, (x, y, t) in enumerate(loader):
            features = model(x.cuda())
            if t is None:
                t = (torch.ones(len(y)) * task_id).long()

            if task_id == 0:
                encoded_dataset = H5Dataset(features.cpu(), y, t, data_path=filename)
            else:
                encoded_dataset.add_data(features.cpu(), y, t)

    return encoded_dataset


def encode_scenario(scenario, model, batch_size, file_name, train=True):
    if os.path.isfile(file_name):
        raise ValueError("File name already exists")

    print(f"Encoding {file_name}")
    encoded_dataset = encode_into_dataset(model, scenario, batch_size, file_name, train)

    return ContinualScenario(encoded_dataset)
