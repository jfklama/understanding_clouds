import os
import argparse
import json

from typing import Mapping

import numpy as np
import torch
import torchvision

from torch.utils.data import DataLoader

from loggify import Loggify

from understanding_clouds.datasets.mask_unet_dataset import UnetDataset



class CloudsUnet:
    def __init__(self, experiment_dirpath: str, init_lr: float = 0.0001, weight_decay: float = 0.005, gamma: float = 0.9):
        self.experiment_dirpath = experiment_dirpath
        self.init_lr = init_lr
        self.weight_decay = weight_decay
        self.gamma = gamma
        self.device = torch.device(
            'cuda' if torch.cuda.is_available() else 'cpu')

        self.net = get_mask_unet_net(4).to(self.device)
        params = [p for p in self.net.parameters()
                  if p.requires_grad == True]
        self.loss_fn = torch.nn.MSELoss() # wrong, but left for now
        self.optimizer = torch.optim.Adam(
            params, lr=self.init_lr, weight_decay=self.weight_decay)

        self.lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(
            optimizer=self.optimizer, gamma=self.gamma)

        os.makedirs(self.experiment_dirpath, exist_ok=True)

    def train(self, dataloader: torch.utils.data.DataLoader, epochs: int, snapshot_frequency: int = 10):

        optimizer = self.optimizer
        loss_fn = self.loss_fn
        model = self.net

        loss_list = []

        print('Beginning training...')
        print('Using cuda...' if torch.cuda.is_available() else 'Using cpu...')

        for i, epoch in enumerate(range(1, epochs + 1)):
            print(f'Epoch {epoch}')
            model.train()

            loss_tmp = []

            for image, masks in dataloader:
                optimizer.zero_grad()
                output = model(image)
                loss = loss_fn(output, masks)
                loss_tmp.append(loss.item())

                loss.backward()
                optimizer.step()

            loss_list.append( np.mean(loss_tmp) )
            if i % snapshot_frequency == 0:
                    self.save_model(epoch)
        print('Training done!')
        print('Loss list: ', loss_list)
        print('Saving model...')
        self.save_model(epoch)
        print('Ready!')

    def save_model(self, epoch):
        os.makedirs(self.experiment_dirpath, exist_ok=True)
        checkpoint = {'epoch': epoch,
                      'state_dict': self.net.state_dict(),
                      'optimizer': self.optimizer.state_dict(),
                      'lr_scheduler': self.lr_scheduler.state_dict()}
        torch.save(checkpoint, os.path.join(
            self.experiment_dirpath, 'model.pth'))

    def load_model(self, model_path):
        checkpoint = torch.load(model_path)
        self.net.load_state_dict(checkpoint['state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.lr_scheduler.load_state_dict(checkpoint['lr_scheduler'])
        print('Model loaded successfully!')


def get_mask_unet_net(num_classes):
    model = torch.hub.load('mateuszbuda/brain-segmentation-pytorch', 'unet',
                            in_channels=3, out_channels=num_classes, init_features=32, pretrained=False)
    return model


def parse_args():
    parser = argparse.ArgumentParser(
        description='Use regression for OMTF')

    parser.add_argument('-e', '--epochs', help="Number of epochs",
                        type=int, default=10)
    parser.add_argument(
        '--init_lr', help='Initial learning_rate', type=float, default=0.0001)
    parser.add_argument('-trb', '--train_batch_size',
                        help="Trian batch size", type=int, default=1)
    parser.add_argument('--experiment_dirpath',
                        help='Where to save the model', required=True, type=str)
    parser.add_argument('--pretrained_model_path', help='Path to pretrained model',
                        type=str, default=None)
    parser.add_argument(
        '--data_path', help='Path to data', required=True, type=str)
    parser.add_argument('--gamma',
                        default=0.9, type=float)
    parser.add_argument('--weight_decay',
                        default=0.005, type=float)
    parser.add_argument('--subsample', default=100, type=int)
    args = parser.parse_args()
    return args


def main_without_args(args):
    print('Loading dataset...')
    train_dataset = UnetDataset(images_dirpath=args.data_path, subsample = args.subsample)
    print('Ready!')
    print('Preparing dataloader...')
    #dataloader = DataLoader( train_dataset, batch_size=args.train_batch_size, shuffle=True )
    print('Ready!')
    print('Declaring model...')
    clouds_model = CloudsUnet(experiment_dirpath=args.experiment_dirpath,
                                  init_lr=args.init_lr, weight_decay=args.weight_decay, gamma=args.gamma)
    print('Ready!')
    if args.pretrained_model_path is not None:
        args.pretrained_model_path = os.path.abspath(
            args.pretrained_model_path)
        clouds_model.load_model(args.pretrained_model_path)

    print('Initiating training...')
    clouds_model.train(DataLoader( train_dataset, batch_size=args.train_batch_size, shuffle=True ),
                       args.epochs)
    training_params = {'epochs': args.epochs,
                       'init_lr': args.init_lr,
                       'train_batch_size': args.train_batch_size,
                       'data_path': os.path.abspath(args.data_path),
                       'weight_decay': args.weight_decay,
                       'gamma': args.gamma,
                       'pretrained_model_path': args.pretrained_model_path or None}

    with open(os.path.join(args.experiment_dirpath, 'training_params.json'), 'w') as f:
        json.dump(training_params, f)


def main():
    args = parse_args()
    os.makedirs(args.experiment_dirpath, exist_ok=True)
    with Loggify(os.path.join(args.experiment_dirpath, 'log.txt')):
        main_without_args(args)


if __name__ == '__main__':
    main()
