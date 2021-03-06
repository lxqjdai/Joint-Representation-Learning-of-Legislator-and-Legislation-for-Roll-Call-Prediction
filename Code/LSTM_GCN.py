#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
import json
from pprint import pprint
import nltk
from nltk.corpus import stopwords
import numpy as np
from trash import get_all_data
import torch.nn.functional as F
from torch import optim
import random
import time
import argparse
import copy
import pandas as pd
from sklearn.metrics import classification_report

def normalize(A , symmetric=True):
        # A = A+I
    A = A + torch.eye(A.size(0)).to(cuda0)
    # 所有节点的度
    d = A.sum(1)
    if symmetric:
        #D = D^-1/2
        D = torch.diag(torch.pow(d , -0.5))
        return D.mm(A).mm(D)
    else :
        # D=D^-1
        D =torch.diag(torch.pow(d,-1))
        return D.mm(A)

class GCN(nn.Module):
    '''
    Z = AXW
    '''
    def __init__(self , dim_in , dim_hidden, dim_out):
        super(GCN,self).__init__()
        self.fc1 = nn.Linear(dim_in ,dim_hidden,bias=False)
        self.fc2 = nn.Linear(dim_hidden,dim_out,bias=False)
        #self.fc1 = nn.Linear(dim_in ,dim_out,bias=False)

    def forward(self,A,X):
        '''
        计算俩层gcn
        '''
        self.A = A
        X = F.relu(self.fc1(self.A.mm(X)))
        return self.fc2(self.A.mm(X))
        #return X


class member_gcn(nn.Module):
    def __init__(self,  member_size, state_size,party_size):
        super(member_gcn,self).__init__()
        self.member_embedding = nn.Embedding(member_size, 16)
        self.party_embedding = nn.Embedding(party_size, 8)
        self.state_embeddding = nn.Embedding(state_size, 8)
        self.bn1 = nn.BatchNorm1d(32)
        self.gcn = GCN(32, 32, 32)
    def forward(self, member, state, party, adjacent_matrix_hat):
        member_embed = self.member_embedding(member)
        party_embed = self.party_embedding(party)
        state_embed = self.state_embeddding(state)
        legislator_embem = torch.cat([member_embed, party_embed, state_embed], dim=1)
        legislator_embem = self.bn1(legislator_embem)
        adj_normed = normalize(adjacent_matrix_hat)
        gcn_out = self.gcn(adj_normed,legislator_embem)
        return gcn_out


class LSTM_GCN(nn.Module):
    def __init__(self, word_embed_dim, hidden_dim, lstm_out_dim, vocab_size, member_size, state_size,party_size):
        super(LSTM_GCN, self).__init__()
        self.lstm_out_dim = lstm_out_dim
        self.hidden_dim = hidden_dim
        self.word_embed_dim = word_embed_dim
        # self.w0 = torch.rand(self.lstm_out_dim + 32, gcn0_dim, dtype=torch.float64)
        # self.w1 = torch.rand(gcn0_dim, 3, dtype=torch.float64)
        self.legislation_embedding = nn.Embedding(vocab_size, word_embed_dim)
        self.lstm = nn.LSTM(word_embed_dim, lstm_out_dim)
        self.member_embed = member_gcn(member_size,state_size,party_size)
        self.mlp1 = nn.Linear(64,32)
        self.mlp2 = nn.Linear(32,3)

    def forward(self, sentence, member_all, state_all, party_all, mask_size, adjacent_matrix):
        # embeding the legislation
        legislation_embed = self.legislation_embedding(sentence)
        # padding
        legislation_embed = torch.cat([legislation_embed, legislation_embed.new_zeros([32 - legislation_embed.size(0),self.word_embed_dim])], 0)
        _, out = self.lstm(legislation_embed.view(32, 1, -1))
        lstm_out = out[0][0]
        lstm_out = lstm_out.expand(len(member_all), self.lstm_out_dim)

        # embeding the legislator
        gcn_out = self.member_embed(member_all, state_all, party_all, adjacent_matrix)
        
        # cat the legislator and the legislation
        total_embed = torch.cat([gcn_out,lstm_out], dim=1)

        # MLP
        x = self.mlp1(total_embed)
        x = self.mlp2(x)
        return x

def sen2index(sen):
    words = nltk.word_tokenize(sen)
    index_ls = []
    for word in words:
        if str.lower(word) in word_dict:
            index_ls.append(word_dict[str.lower(word)])
    if len(index_ls)>32:
        index_ls = index_ls[0:32]
    return torch.tensor(index_ls, dtype=torch.long).to(cuda0)

def get_all_mem_info(member_info):
    member_size = len(member_info)
    member_all = np.array(range(member_size))
    state_all = np.zeros(member_size)
    party_all = np.zeros(member_size)
    for i in range(member_size):
        state_all[i], party_all[i] = member_info[i]
    return member_all, state_all, party_all 
    


def member2index(vote_data, member_size):
    member_all, state_all, party_all = get_all_mem_info(member_info)
    vote_result = np.zeros(member_size)
    vote_result_dict = {0:[],1:[],2:[]}
    y_mask = np.zeros(member_size)
    # get the vote data
    for vote in vote_data:
        if vote == 'basic_information' or vote_data[vote]['Vote'] not in vote_dict:
            continue
        record = vote_data[vote]
        vote_result_dict[vote_dict[record['Vote']]].append(member_dict[vote])
        state_all[member_dict[vote]] = state_dict[record['State']]
        party_all[member_dict[vote]] = party_dict[record['Party']]
        vote_result[member_dict[vote]] = vote_dict[record['Vote']]
        if vote in train_member:
            y_mask[member_dict[vote]] = 1
    vote_num = [len(vote_result_dict[tmp]) for tmp in vote_result_dict]
    return torch.tensor(member_all, dtype=torch.long).to(cuda0), torch.tensor(state_all, dtype=torch.long).to(cuda0), \
        torch.tensor(party_all, dtype=torch.long).to(cuda0), torch.tensor(vote_result, dtype=torch.long).to(cuda0), \
        torch.tensor(y_mask, dtype=torch.float).to(cuda0)

def main(args):
    # define model
    lstmgcn_model = LSTM_GCN(word_embeddim, lstm_outdim, lstm_outdim,
                                len(word_dict), len(member_dict), len(state_dict), len(party_dict)).to(cuda0)
    loss_fun = nn.CrossEntropyLoss(reduction='none')
    optimizer = optim.Adam(lstmgcn_model.parameters(), lr=args.lr)

    # some set up for training
    train_name_list = [name for name in train]
    random.shuffle(train_name_list)
    val_name_list = train_name_list[:len(train_name_list)//5]
    train_name_list = train_name_list[len(train_name_list)//5:]
    count = 0
    loss_avg = 0
    best_acc = 0
    epoch = 0

    # begin training
    while True:
        print('epoch' + str(epoch))
        for legislation_name in train_name_list:
            count += 1
            
            # evaluations
            if count % 50 == 1:
                print('Loss of Train set is %.4f' % (loss_avg/200.0))
                loss_avg = 0
                total = 0
                right = 0
                with torch.no_grad():
                    real_freq = {0: 0, 1: 0, 2: 0}
                    predict_freq = {0: 0, 1: 0, 2: 0}
                    for legislation_name1 in val_name_list:
                        if 'Official Title as Introduced' not in k[legislation_name1]['title']:
                            title_key = 'Official Titles as Introduced'
                        else:
                            title_key = 'Official Title as Introduced'
                        legislation_input = sen2index(
                            train[legislation_name1]['basic_information']['Descrption']+' '+k[legislation_name1]['title'][title_key])
                        if legislation_input.size()[0] == 0:
                            continue
                        
                        member_input, state_input, party_input, gt_result, y_mask  = member2index(train[legislation_name1],len(member_dict))
                        if len(member_input) == 0:
                            continue

                        # out put from the network
                        output = lstmgcn_model(legislation_input, member_input, state_input, party_input,len(member_input),adjacent_matrix)
                        
                        # calculate loss
                        loss = loss_fun(output, gt_result)
                        loss = torch.mean(torch.mul(loss,y_mask))
                        
                        # compute the accuracy
                        y_mask = y_mask.cpu().numpy()
                        pred_result = torch.argmax(output, dim=1).cpu().numpy()
                        gt_result = gt_result.cpu().numpy()
                        right += sum(np.multiply(pred_result == gt_result,y_mask))
                        total += sum(y_mask)
                        for i in range(len(pred_result)):
                            predict_freq[pred_result[i]] += 1
                            real_freq[gt_result[i]] += 1
                # the frequence of different classes
                print('----- predict_freq -----')
                print(predict_freq)
                print('----- real_freq -----')
                print(real_freq)
                # save the best model and early stop
                if best_acc < (right / total):
                    best_acc = (right / total)
                    best_model = LSTM_GCN(word_embeddim, lstm_outdim, lstm_outdim,
                                len(word_dict), len(member_dict), len(state_dict), len(party_dict)).to(cuda0)
                    best_model.load_state_dict(copy.deepcopy(lstmgcn_model.state_dict()))
                    early_stop_count = 0
                early_stop_count += 1
                if early_stop_count >=15:
                    break
                print('LSTM_GCN direct prediction acc:' + str(right / total) + '\t'+ '\t' + 'epoch:' + str(epoch) +
                       '\t\t' + 'Data: '+str(time_end-time_len)+'-'+str(time_end)+'\t'+'Best acc:'+str(best_acc))
            
            # get the data prepared
            if 'Official Title as Introduced' not in k[legislation_name]['title']:
                title_key = 'Official Titles as Introduced'
            else:
                title_key = 'Official Title as Introduced'
            legislation_input = sen2index(
                train[legislation_name]['basic_information']['Descrption']+' '+k[legislation_name]['title'][title_key])
            if legislation_input.size()[0] == 0:
                continue
            member_input, state_input, party_input, gt_result, y_mask  = member2index(train[legislation_name],len(member_dict))

            if member_input is None:
                continue
            
            output = lstmgcn_model(
                legislation_input, member_input, state_input, party_input, len(member_input), adjacent_matrix)
            
            # calculate loss
            loss = loss_fun(output, gt_result)
            loss = torch.mean(torch.mul(loss,y_mask))
            loss_avg += loss.item()
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        epoch += 1
        if early_stop_count>=15:
            break
    return best_acc, best_model


def prediction_on_test(args,best_model, test):
    best_model.eval()
    # prediction on test set
    total = 0
    right = 0
    gt_result_all = []
    pred_result_all = []
    pred_result_gt_all = []
    with torch.no_grad():
        for legislation_name1 in test:
            if 'Official Title as Introduced' not in k[legislation_name1]['title']:
                title_key = 'Official Titles as Introduced'
            else:
                title_key = 'Official Title as Introduced'
            legislation_input = sen2index(
                test[legislation_name1]['basic_information']['Descrption']+' '+k[legislation_name1]['title'][title_key])
            if legislation_input.size()[0] == 0:
                continue
            
            member_input, state_input, party_input, gt_result, y_mask  = member2index(test[legislation_name1],len(member_dict))
            if len(member_input) == 0:
                continue

            # out put from the network
            output = best_model(legislation_input, member_input, state_input, party_input,len(member_input),adjacent_matrix)
            
            # compute the accuracy
            y_mask = y_mask.cpu().numpy()
            pred_result = torch.argmax(output, dim=1).cpu().numpy()
            gt_result = gt_result.cpu().numpy()
            right += sum(np.multiply(pred_result == gt_result,y_mask))
            total += sum(y_mask)
            gt_result_all.append(np.squeeze(gt_result[y_mask==1]))
            pred_result_all.append(np.squeeze(pred_result[y_mask==1]))


    # compute the recall and f1 score
    gt_result_all = np.concatenate(gt_result_all)
    pred_result_all = np.concatenate(pred_result_all)
    target_names = ['Yes','Not vote','No']
    metrics = classification_report(gt_result_all, pred_result_all, target_names=target_names,output_dict=True)
    wei_recall=metrics['weighted avg']['recall']
    micro_recall = metrics['micro avg']['recall']
    wei_f1 = metrics['weighted avg']['f1-score']
    micro_f1 = metrics['micro avg']['f1-score']

    return right/total, wei_recall, micro_recall, wei_f1, micro_f1



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='HyperParameters for String Embedding')
    parser.add_argument('--epochs', type=int, default=100,
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--word_dim', type=int, default=32,
                        help='word dimension')
    parser.add_argument('--lr', type=float, default=0.0001,
                        help='learning rate')
    parser.add_argument('--version', type=int, default=1,
                    help='version info')
    parser.add_argument('--eval', type=int, default=100,
                    help='evaluation frequency')
    parser.add_argument('--load', type=int, default=0,
                    help='load trained model')
    parser.add_argument('--time_end', type=int, default=2017,
                    help='whether to check result')
    parser.add_argument('--time_len', type=int, default=4,
                    help='whether to check result')
    parser.add_argument('--cuda', type=int, default=0,
                    help='whether to check result')
    parser.add_argument('--result', type=str, default='lstm_gcn_direct_predict',
                    help='define the name for result file')
    args = parser.parse_args()
    cuda0 = torch.device('cuda:{}'.format(args.cuda))
    # parameters
    word_embeddim = 100
    lstm_outdim = args.word_dim
    word_dict_len = 20000
    time_end = args.time_end
    time_len = args.time_len

    # load data
    with open('word_dict.json') as f:
        word_dict_all = json.load(f)
    word_dict = {}
    all_word = list(word_dict_all)
    for i in range(word_dict_len):
        word_dict[all_word[i]] = word_dict_all[all_word[i]]
    with open('legislation.json') as k:
        k = json.load(k)
    with open('house_vote.json') as f:
        house_vote = json.load(f)
    vote_dict = {'Yea': 0, 'Aye': 0, 'Nay': 2,
                 'No': 2, 'Not Voting': 1, 'Present': 1}
    acc_test = []
    acc_val = []
    wei_recall_all, micro_recall_all, wei_f1_all, micro_f1_all, wei_recall_gt_all, micro_recall_gt_all, wei_f1_gt_all, micro_f1_gt_all = [],[],[],[],[],[],[],[]
    for time_end in range(2005,2018):
        train, test, member_dict, state_dict, party_dict, member_info, adjacent_matrix = get_all_data(
            time_end-time_len, time_end,load=False)

        # get the menber in training data
        train_member = []
        for leg in train:
            for member in train[leg]:
                if member == 'basic_information':
                    continue
                if member not in train_member:
                    train_member.append(member)

        adjacent_matrix = torch.tensor(adjacent_matrix, dtype=torch.float32).to(cuda0)
        acc_val_, best_model = main(args)
        test_acc, wei_recall, micro_recall, wei_f1, micro_f1 = prediction_on_test(args, best_model, test)
        wei_recall_all.append(wei_recall); micro_recall_all.append(micro_recall); wei_f1_all.append(wei_f1); micro_f1_all.append(micro_f1)
        acc_test.append(test_acc)
        acc_val.append(acc_val_) 
        print('Runing acc: %.6f' % np.mean(acc_test))
    acc_val = np.array(acc_val)
    acc_test = np.array(acc_test)
    result = pd.DataFrame({'test acc':acc_test,'val acc':acc_val})
    result1 = pd.DataFrame({'wei_recall':wei_recall_all,'micro_recall':micro_recall_all, 'wei_f1':wei_f1_all, 'micro_f1':micro_f1_all})
    result.to_csv('{}.csv'.format(args.result))
    result1.to_csv('{}_recall_f1.csv'.format(args.result))
    print('LSTM_GCN Final acc: %.6f' % np.mean(acc_test))